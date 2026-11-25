"""Protected acceptance tests for Story S1-03 (F-03: Schemas, Grounding & 4-Agent Topology)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from app.schemas import (
    ActionOwner,
    AlignmentFinding,
    AlignmentReport,
    AlignmentStatus,
    RootCauseCategory,
    SchemaValidationError,
    Severity,
    render_executive_scorecard,
    verify_report_citations,
)


def _sample_finding(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
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
        "rationale": "TDD selects a US region despite explicit EU residency constraint.",
        "recommended_action": "Move Firestore database location to europe-west1 or europe-west3.",
    }
    base.update(overrides)
    return base


class TestSchemasAndGrounding(unittest.TestCase):
    """Verify Pydantic v2 alignment schemas, 6 root-cause enums, and citation verification."""

    def test_all_six_drift_root_causes_and_statuses_exist(self) -> None:
        expected_causes = {
            "ALIGNED",
            "INTENTIONAL_TRADEOFF",
            "ACCIDENTAL_OMISSION",
            "UNDOCUMENTED_CONTRADICTION",
            "UNJUSTIFIED_SCOPE_CREEP",
            "AMBIGUOUS_PRD_SPEC",
            "STALE_OR_MISSING_PRD_SPEC",
        }
        self.assertEqual({c.value for c in RootCauseCategory}, expected_causes)
        self.assertIn("PRD_BACKFILL_REQUIRED", {s.value for s in AlignmentStatus})
        self.assertIn("PM / T/PgM", {o.value for o in ActionOwner})

    def test_valid_alignment_report_round_trip_and_json_schema(self) -> None:
        backfill = _sample_finding(
            finding_id="GAP-002",
            requirement_ref="TDD-ONLY",
            title="Refund approval threshold added from Finance sync without PRD update",
            alignment_status="PRD_BACKFILL_REQUIRED",
            severity="Medium",
            root_cause_category="STALE_OR_MISSING_PRD_SPEC",
            action_owner="PM / T/PgM",
            prd_section="None",
            prd_quote="Not present in PRD",
            tdd_section="Refund Rules",
            tdd_quote="Per 11/10 sync with Finance Ops, refunds over $500 route to manual queue.",
            rationale="Concrete business rule built from verbal meeting decision without updating PRD.",
            recommended_action="Ratify $500 threshold and backfill PRD Functional Requirements.",
        )
        payload = {
            "project_key": "checkout-refunds",
            "revision_label": "v1",
            "overall_alignment_score": 68,
            "blocker_count": 1,
            "prd_backfill_count": 1,
            "tdd_fix_count": 1,
            "findings": [_sample_finding(), backfill],
            "delta_from_previous": [],
        }

        report = AlignmentReport.model_validate(payload)
        self.assertEqual(report.project_key, "checkout-refunds")
        self.assertEqual(report.blocker_count, 1)
        self.assertEqual(report.findings[0].severity, Severity.BLOCKER)
        self.assertEqual(
            report.findings[1].root_cause_category,
            RootCauseCategory.STALE_OR_MISSING_PRD_SPEC,
        )

        dumped = report.model_dump(mode="json")
        self.assertEqual(dumped["overall_alignment_score"], 68)
        self.assertEqual(
            dumped["findings"][1]["alignment_status"], "PRD_BACKFILL_REQUIRED"
        )

        schema = AlignmentReport.model_json_schema()
        self.assertIn("properties", schema)
        self.assertIn("findings", schema["properties"])

    def test_schema_rejects_invalid_scores_enums_and_short_titles(self) -> None:
        with self.assertRaises(SchemaValidationError):
            AlignmentReport.model_validate(
                {
                    "project_key": "bad-score",
                    "revision_label": "v1",
                    "overall_alignment_score": 140,
                    "blocker_count": 0,
                    "prd_backfill_count": 0,
                    "tdd_fix_count": 0,
                    "findings": [],
                }
            )

        with self.assertRaises(SchemaValidationError):
            AlignmentFinding.model_validate(
                _sample_finding(root_cause_category="UNKNOWN_CAUSE")
            )

        with self.assertRaises(SchemaValidationError):
            AlignmentFinding.model_validate(_sample_finding(title="Bad"))

        with self.assertRaises(SchemaValidationError):
            AlignmentFinding.model_validate(_sample_finding(action_owner="RandomTeam"))

    def test_verify_report_citations_catches_hallucinated_quotes(self) -> None:
        ingested = {
            "prd": {
                "Security Constraints": "All customer data must remain inside EU datacenters.",
            },
            "tdd": {
                "Data Stores": "Uses Firestore in us-central1 for low-latency writes.",
                "Refund Rules": "Per 11/10 sync with Finance Ops, refunds over $500 route to manual queue.",
            },
        }
        grounded = _sample_finding()
        hallucinated = _sample_finding(
            finding_id="GAP-099",
            prd_quote="Quantum blockchain ledger required for every click.",
            tdd_quote="Uses Firestore in us-central1",
        )
        report = AlignmentReport.model_validate(
            {
                "project_key": "checkout",
                "revision_label": "v1",
                "overall_alignment_score": 50,
                "blocker_count": 2,
                "prd_backfill_count": 0,
                "tdd_fix_count": 2,
                "findings": [grounded, hallucinated],
            }
        ).model_dump(mode="json")

        check = verify_report_citations(report, ingested)
        self.assertEqual(check["total_quotes_checked"], 4)
        self.assertEqual(check["grounded_quotes"], 3)
        self.assertAlmostEqual(check["grounding_rate"], 0.75)
        self.assertEqual(len(check["ungrounded_findings"]), 1)
        self.assertEqual(check["ungrounded_findings"][0]["finding_id"], "GAP-099")

    def test_render_executive_scorecard_separates_tdd_fixes_and_prd_backfills(
        self,
    ) -> None:
        backfill = _sample_finding(
            finding_id="GAP-002",
            requirement_ref="TDD-ONLY",
            title="Refund approval threshold added from Finance sync without PRD update",
            alignment_status="PRD_BACKFILL_REQUIRED",
            severity="Medium",
            root_cause_category="STALE_OR_MISSING_PRD_SPEC",
            action_owner="PM / T/PgM",
            prd_section="None",
            prd_quote="Not present in PRD",
            tdd_section="Refund Rules",
            tdd_quote="Per 11/10 sync with Finance Ops, refunds over $500 route to manual queue.",
        )
        report = AlignmentReport.model_validate(
            {
                "project_key": "checkout-refunds",
                "revision_label": "v1",
                "overall_alignment_score": 68,
                "blocker_count": 1,
                "prd_backfill_count": 1,
                "tdd_fix_count": 1,
                "findings": [_sample_finding(), backfill],
            }
        ).model_dump(mode="json")

        markdown = render_executive_scorecard(report)
        self.assertIn("Engineering TDD Fixes", markdown)
        self.assertIn("PM & T/PgM PRD Backfills", markdown)
        self.assertIn("GAP-001", markdown)
        self.assertIn("GAP-002", markdown)
        self.assertIn("STALE_OR_MISSING_PRD_SPEC", markdown)

    def test_agent_module_declares_four_agent_topology_and_model_routing(self) -> None:
        """Inspect app/agent.py AST to verify multi-agent wiring, Flash/Pro routing, and HITL."""
        agent_path = Path(__file__).resolve().parent.parent / "app" / "agent.py"
        source = agent_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.assertIn("ParallelAgent", source)
        self.assertIn("SequentialAgent", source)
        self.assertIn("prd_goal_extractor", source)
        self.assertIn("tdd_architecture_extractor", source)
        self.assertIn("alignment_analyzer", source)
        self.assertIn("review_action_agent", source)
        self.assertIn("gemini-3.5-flash-lite", source)
        self.assertIn("gemini-3.8-flash", source)
        self.assertIn("require_confirmation=True", source)
        self.assertIn("ResumabilityConfig", source)

        assigned_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for required_symbol in (
            "prd_goal_extractor",
            "tdd_architecture_extractor",
            "parallel_doc_extractors",
            "alignment_analyzer",
            "review_action_agent",
            "alignment_audit_pipeline",
            "root_agent",
            "app",
        ):
            self.assertIn(required_symbol, assigned_names)


if __name__ == "__main__":
    unittest.main()
