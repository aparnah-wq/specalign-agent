"""Protected acceptance tests for Story S1-05 (F-05: HITL Sign-Off Gate & Persistence)."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.storage import SQLiteAuditStore
from app.tools.audit_tools import (
    compute_revision_delta,
    get_previous_audit,
    record_alignment_decision,
)


@dataclass
class FakeToolContext:
    """Minimal stand-in for ADK ToolContext exposing mutable session state."""

    state: dict[str, Any] = field(default_factory=dict)


def _sample_report(blocker_count: int = 1, score: int = 70) -> dict[str, Any]:
    findings = [
        {
            "finding_id": "GAP-001",
            "requirement_ref": "REQ-003",
            "title": "EU data residency conflict in Firestore region",
            "alignment_status": "CONTRADICTION",
            "severity": "Blocker",
            "root_cause_category": "UNDOCUMENTED_CONTRADICTION",
            "action_owner": "Engineering",
            "prd_section": "Security Constraints",
            "prd_quote": "All customer data must remain inside EU datacenters.",
            "tdd_section": "Data Stores",
            "tdd_quote": "Uses Firestore in us-central1.",
            "rationale": "US region conflicts with EU residency.",
            "recommended_action": "Move Firestore to europe-west1.",
        },
        {
            "finding_id": "GAP-002",
            "requirement_ref": "TDD-ONLY",
            "title": "Refund threshold from Finance sync missing in PRD",
            "alignment_status": "PRD_BACKFILL_REQUIRED",
            "severity": "Medium",
            "root_cause_category": "STALE_OR_MISSING_PRD_SPEC",
            "action_owner": "PM / T/PgM",
            "prd_section": "None",
            "prd_quote": "Not present in PRD",
            "tdd_section": "Refund Rules",
            "tdd_quote": "Per 11/10 sync with Finance Ops, refunds over $500 route to manual queue.",
            "rationale": "Verbal decision captured in TDD but not PRD.",
            "recommended_action": "Backfill PRD Functional Requirements.",
        },
    ]
    if blocker_count == 0:
        findings = [findings[1]]
    return {
        "project_key": "checkout-refunds",
        "revision_label": "v1",
        "overall_alignment_score": score,
        "blocker_count": blocker_count,
        "prd_backfill_count": 1,
        "tdd_fix_count": 1 if blocker_count else 0,
        "findings": findings,
        "delta_from_previous": [],
    }


class TestStorageAndHitlGate(unittest.TestCase):
    """Acceptance tests for mandatory HITL confirmation and SQLite/Firestore audit persistence."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test_audits.db"
        self._orig_mode = os.environ.get("SPECALIGN_STORAGE_MODE")
        self._orig_path = os.environ.get("SPECALIGN_SQLITE_PATH")
        os.environ["SPECALIGN_STORAGE_MODE"] = "sqlite"
        os.environ["SPECALIGN_SQLITE_PATH"] = str(self.db_path)

    def tearDown(self) -> None:
        if self._orig_mode is None:
            os.environ.pop("SPECALIGN_STORAGE_MODE", None)
        else:
            os.environ["SPECALIGN_STORAGE_MODE"] = self._orig_mode
        if self._orig_path is None:
            os.environ.pop("SPECALIGN_SQLITE_PATH", None)
        else:
            os.environ["SPECALIGN_SQLITE_PATH"] = self._orig_path
        self._tmpdir.cleanup()

    def test_get_previous_audit_returns_not_found_for_new_project(self) -> None:
        ctx = FakeToolContext()
        res = get_previous_audit(project_key="brand-new-proj", tool_context=ctx)
        self.assertEqual(res["status"], "not_found")
        self.assertIsNone(ctx.state.get("previous_audit"))

    def test_hitl_gate_blocks_write_when_human_confirmed_is_false(self) -> None:
        ctx = FakeToolContext(
            state={"alignment_report": _sample_report(blocker_count=1)}
        )
        res = record_alignment_decision(
            project_key="checkout-refunds",
            revision_label="v1",
            decision_status="Changes Requested",
            approved_ticket_ids=["GAP-001", "GAP-002"],
            reviewer_note="Please resolve before Sprint 1.",
            human_confirmed=False,
            tool_context=ctx,
        )
        self.assertEqual(res["status"], "awaiting_human_confirmation")
        self.assertEqual(res["blocker_count"], 1)
        self.assertEqual(res["prd_backfill_count"], 1)
        self.assertIn("hitl_pending_decision", ctx.state)

        store = SQLiteAuditStore(self.db_path)
        self.assertIsNone(store.get_latest_audit("checkout-refunds"))
        self.assertEqual(store.list_gap_tickets("checkout-refunds"), [])

    def test_approving_with_open_blockers_requires_explicit_risk_waiver_note(
        self,
    ) -> None:
        ctx = FakeToolContext(
            state={"alignment_report": _sample_report(blocker_count=1)}
        )
        blocked = record_alignment_decision(
            project_key="checkout-refunds",
            revision_label="v1",
            decision_status="Approved",
            approved_ticket_ids=["GAP-001"],
            reviewer_note="",
            human_confirmed=True,
            tool_context=ctx,
        )
        self.assertEqual(blocked["status"], "error")
        self.assertEqual(blocked["error_code"], "BLOCKER_WAIVER_REQUIRED")
        self.assertIn("recovery_guidance", blocked)

        store = SQLiteAuditStore(self.db_path)
        self.assertIsNone(store.get_latest_audit("checkout-refunds"))

        waived = record_alignment_decision(
            project_key="checkout-refunds",
            revision_label="v1",
            decision_status="Approved",
            approved_ticket_ids=["GAP-001"],
            reviewer_note="Waived for sandbox pilot; EU migration tracked for GA.",
            human_confirmed=True,
            tool_context=ctx,
        )
        self.assertEqual(waived["status"], "success")
        self.assertTrue(waived["risk_waiver_applied"])

    def test_confirmed_decision_persists_baseline_and_gap_tickets_for_next_session(
        self,
    ) -> None:
        ctx_v1 = FakeToolContext(
            state={"alignment_report": _sample_report(blocker_count=1)}
        )
        saved = record_alignment_decision(
            project_key="checkout-refunds",
            revision_label="v1",
            decision_status="Changes Requested",
            approved_ticket_ids=["GAP-001", "GAP-002"],
            reviewer_note="Fix Firestore region and backfill PRD.",
            human_confirmed=True,
            tool_context=ctx_v1,
        )
        self.assertEqual(saved["status"], "success")
        self.assertEqual(len(saved["created_tickets"]), 2)
        self.assertTrue(
            all(t["ticket_id"].startswith("TICKET-") for t in saved["created_tickets"])
        )
        self.assertIsNone(ctx_v1.state.get("hitl_pending_decision"))

        ctx_v2 = FakeToolContext()
        prev = get_previous_audit(project_key="checkout-refunds", tool_context=ctx_v2)
        self.assertEqual(prev["status"], "success")
        self.assertEqual(prev["audit"]["revision_label"], "v1")
        self.assertEqual(prev["audit"]["blocker_count"], 1)
        self.assertEqual(len(prev["open_tickets"]), 2)
        self.assertIsNotNone(ctx_v2.state.get("previous_audit"))

    def test_compute_revision_delta_tracks_closed_open_and_new_findings(self) -> None:
        prev_audit = _sample_report(blocker_count=1, score=68)
        v2_report = {
            "project_key": "checkout-refunds",
            "revision_label": "v2",
            "overall_alignment_score": 88,
            "blocker_count": 0,
            "prd_backfill_count": 1,
            "tdd_fix_count": 1,
            "findings": [
                prev_audit["findings"][1],
                {
                    "finding_id": "GAP-003",
                    "requirement_ref": "REQ-009",
                    "title": "Latency target vague in updated PRD",
                    "alignment_status": "PARTIALLY_COVERED",
                    "severity": "Low",
                    "root_cause_category": "AMBIGUOUS_PRD_SPEC",
                    "action_owner": "PM",
                    "prd_section": "SLAs",
                    "prd_quote": "Responses should be fast.",
                    "tdd_section": "Performance",
                    "tdd_quote": "Assumes 3s p95.",
                    "rationale": "PRD does not specify numeric latency.",
                    "recommended_action": "Add exact p95 target to PRD.",
                },
            ],
        }

        delta = compute_revision_delta(prev_audit, v2_report)
        self.assertEqual(delta["score_change"], 20)
        self.assertEqual(delta["closed_finding_ids"], ["GAP-001"])
        self.assertEqual(delta["still_open_finding_ids"], ["GAP-002"])
        self.assertEqual(delta["new_finding_ids"], ["GAP-003"])


if __name__ == "__main__":
    unittest.main()
