"""Protected acceptance tests for Story S1-06 (F-06: Revision Diff & Async Memory Bank)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.callbacks import add_session_to_memory_callback
from app.tools.audit_tools import (
    compute_revision_delta,
    get_previous_audit,
    record_alignment_decision,
)


@dataclass
class _FakeCallbackContext:
    should_fail_no_memory: bool = False
    calls: int = 0
    state: dict[str, Any] = field(default_factory=dict)

    async def add_session_to_memory(self) -> None:
        self.calls += 1
        if self.should_fail_no_memory:
            raise ValueError(
                "Memory service is not configured in local in-memory mode."
            )


class TestRevisionDeltaAndMemory(unittest.TestCase):
    """Verify async Memory Bank write callback, PreloadMemoryTool wiring, and v1->v2 persistence."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "revision_memory.db"
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

    def test_async_memory_callback_persists_session_without_blocking(self) -> None:
        ctx = _FakeCallbackContext(should_fail_no_memory=False)
        res = asyncio.run(add_session_to_memory_callback(ctx))
        self.assertIsNone(res)
        self.assertEqual(ctx.calls, 1)

    def test_async_memory_callback_handles_missing_local_memory_service_gracefully(
        self,
    ) -> None:
        ctx = _FakeCallbackContext(should_fail_no_memory=True)
        res = asyncio.run(add_session_to_memory_callback(ctx))
        self.assertIsNone(res)
        self.assertEqual(ctx.calls, 1)

    def test_cross_session_v1_to_v2_delta_lifecycle(self) -> None:
        v1_report = {
            "project_key": "billing-api",
            "revision_label": "v1",
            "overall_alignment_score": 65,
            "blocker_count": 1,
            "prd_backfill_count": 1,
            "tdd_fix_count": 1,
            "findings": [
                {
                    "finding_id": "GAP-001",
                    "requirement_ref": "REQ-001",
                    "title": "Missing audit logging requirement in TDD",
                    "alignment_status": "MISSING",
                    "severity": "Blocker",
                    "root_cause_category": "ACCIDENTAL_OMISSION",
                    "action_owner": "Engineering",
                    "prd_section": "Compliance",
                    "prd_quote": "Write immutable audit logs for every refund.",
                    "tdd_section": "None",
                    "tdd_quote": "Not present in TDD",
                    "rationale": "Omitted from TDD.",
                    "recommended_action": "Add Cloud Audit Logging pipeline to TDD.",
                },
                {
                    "finding_id": "GAP-002",
                    "requirement_ref": "TDD-ONLY",
                    "title": "Refund retry limit added from ops sync without PRD update",
                    "alignment_status": "PRD_BACKFILL_REQUIRED",
                    "severity": "Medium",
                    "root_cause_category": "STALE_OR_MISSING_PRD_SPEC",
                    "action_owner": "PM / T/PgM",
                    "prd_section": "None",
                    "prd_quote": "Not present in PRD",
                    "tdd_section": "Retries",
                    "tdd_quote": "Per ops sync, cap retries at 3.",
                    "rationale": "Built from verbal sync.",
                    "recommended_action": "Backfill retry cap into PRD.",
                },
            ],
        }

        session1 = _FakeCallbackContext(state={"alignment_report": v1_report})
        s1_res = record_alignment_decision(
            project_key="billing-api",
            revision_label="v1",
            decision_status="Changes Requested",
            approved_ticket_ids=["GAP-001", "GAP-002"],
            reviewer_note="Resolve GAP-001 and backfill GAP-002.",
            human_confirmed=True,
            tool_context=session1,
        )
        self.assertEqual(s1_res["status"], "success")

        session2 = _FakeCallbackContext()
        prev = get_previous_audit(project_key="billing-api", tool_context=session2)
        self.assertEqual(prev["status"], "success")

        v2_report = {
            "project_key": "billing-api",
            "revision_label": "v2",
            "overall_alignment_score": 92,
            "blocker_count": 0,
            "prd_backfill_count": 1,
            "tdd_fix_count": 0,
            "findings": [v1_report["findings"][1]],
        }
        delta = compute_revision_delta(session2.state["previous_audit"], v2_report)
        self.assertEqual(delta["closed_finding_ids"], ["GAP-001"])
        self.assertEqual(delta["still_open_finding_ids"], ["GAP-002"])
        self.assertEqual(delta["score_change"], 27)

        v2_report["delta_from_previous"] = delta["delta_summary"]
        session2.state["alignment_report"] = v2_report
        s2_res = record_alignment_decision(
            project_key="billing-api",
            revision_label="v2",
            decision_status="Approved",
            approved_ticket_ids=["GAP-002"],
            reviewer_note="Blocker closed; PM backfilling GAP-002 in parallel.",
            human_confirmed=True,
            tool_context=session2,
        )
        self.assertEqual(s2_res["status"], "success")
        self.assertFalse(s2_res["risk_waiver_applied"])

    def test_agent_wiring_includes_memory_bank_guardrails_and_context_compaction(
        self,
    ) -> None:
        agent_source = (
            Path(__file__).resolve().parent.parent / "app" / "agent.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PreloadMemoryTool", agent_source)
        self.assertIn("add_session_to_memory_callback", agent_source)
        self.assertIn("before_model_guardrail_callback", agent_source)
        self.assertIn("ContextFilterPlugin", agent_source)


if __name__ == "__main__":
    unittest.main()
