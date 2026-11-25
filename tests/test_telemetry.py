"""Protected acceptance tests for Story S1-04 (F-04: Telemetry, Logging & 7-Case Golden Suite)."""

from __future__ import annotations

import ast
import io
import json
import logging
import unittest
from pathlib import Path

from app.telemetry import JsonLogFormatter, get_structured_logger, trace_tool_call


class TestTelemetryAndGoldenSuite(unittest.TestCase):
    """Verify structured JSON intent/outcome logging, zero bare prints, and 7-case golden fixtures."""

    def test_trace_tool_call_logs_intent_and_outcome_without_raw_text_or_pii(
        self,
    ) -> None:
        stream = io.StringIO()
        logger = get_structured_logger("specalign.test_telemetry")
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        @trace_tool_call(logger_name="specalign.test_telemetry")
        def sample_ingest(doc_role: str, raw_text: str) -> dict[str, object]:
            return {"status": "success", "doc_role": doc_role, "section_count": 2}

        out = sample_ingest(
            doc_role="prd",
            raw_text="Confidential secret alice@example.com SSN 123-45-6789",
        )
        self.assertEqual(out["status"], "success")

        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)

        intent_event = json.loads(lines[0])
        outcome_event = json.loads(lines[1])

        self.assertEqual(intent_event["event_type"], "tool_intent")
        self.assertEqual(intent_event["tool_name"], "sample_ingest")
        raw_log_blob = stream.getvalue()
        self.assertNotIn("alice@example.com", raw_log_blob)
        self.assertNotIn("123-45-6789", raw_log_blob)
        self.assertNotIn("Confidential secret", raw_log_blob)
        self.assertIn("raw_text_sha256", intent_event["arguments"])

        self.assertEqual(outcome_event["event_type"], "tool_outcome")
        self.assertEqual(outcome_event["tool_name"], "sample_ingest")
        self.assertEqual(outcome_event["status"], "success")
        self.assertGreaterEqual(outcome_event["latency_ms"], 0.0)
        self.assertEqual(intent_event["trace_id"], outcome_event["trace_id"])

    def test_trace_tool_call_logs_exception_outcome_before_reraising(self) -> None:
        stream = io.StringIO()
        logger = get_structured_logger("specalign.test_telemetry_exc")
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        @trace_tool_call(logger_name="specalign.test_telemetry_exc")
        def failing_tool(project_key: str) -> dict[str, object]:
            raise RuntimeError(f"Simulated backend timeout for {project_key}")

        with self.assertRaises(RuntimeError):
            failing_tool(project_key="payments-api")

        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        intent_event = json.loads(lines[0])
        outcome_event = json.loads(lines[1])
        self.assertEqual(intent_event["event_type"], "tool_intent")
        self.assertEqual(outcome_event["event_type"], "tool_outcome")
        self.assertEqual(outcome_event["status"], "exception")
        self.assertEqual(outcome_event["error_code"], "RuntimeError")
        self.assertEqual(intent_event["trace_id"], outcome_event["trace_id"])

    def test_zero_bare_print_calls_inside_app_package(self) -> None:
        app_dir = Path(__file__).resolve().parent.parent / "app"
        for py_file in sorted(app_dir.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    self.fail(f"Found bare print() call in {py_file}:{node.lineno}")

    def test_seven_case_golden_fixtures_and_adk_eval_set_contract(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        fixtures_root = repo_root / "evals" / "fixtures"
        expected_cases = [
            ("tc01_clean", "ALIGNED"),
            ("tc02_omission", "ACCIDENTAL_OMISSION"),
            ("tc03_contradiction", "UNDOCUMENTED_CONTRADICTION"),
            ("tc04_tradeoff", "INTENTIONAL_TRADEOFF"),
            ("tc05_scope_creep", "UNJUSTIFIED_SCOPE_CREEP"),
            ("tc06_ambiguous_pii", "AMBIGUOUS_PRD_SPEC"),
            ("tc07_stale_prd_verbal", "STALE_OR_MISSING_PRD_SPEC"),
        ]
        for folder_name, expected_cause in expected_cases:
            case_dir = fixtures_root / folder_name
            self.assertTrue(case_dir.is_dir(), f"Missing fixture directory: {case_dir}")
            self.assertTrue((case_dir / "prd.md").is_file())
            self.assertTrue((case_dir / "tdd.md").is_file())
            expected_path = case_dir / "expected.json"
            self.assertTrue(expected_path.is_file())
            expected_meta = json.loads(expected_path.read_text(encoding="utf-8"))
            self.assertEqual(
                expected_meta["expected_primary_root_cause"], expected_cause
            )

        eval_set_path = repo_root / "evals" / "specalign_golden.test.json"
        eval_cfg_path = repo_root / "evals" / "eval_config.json"
        self.assertTrue(eval_set_path.is_file())
        self.assertTrue(eval_cfg_path.is_file())

        eval_set = json.loads(eval_set_path.read_text(encoding="utf-8"))
        self.assertIn("eval_set_id", eval_set)
        self.assertEqual(len(eval_set["eval_cases"]), 7)
        for case in eval_set["eval_cases"]:
            self.assertIn("eval_id", case)
            self.assertGreaterEqual(len(case["conversation"]), 1)
            turn = case["conversation"][0]
            self.assertIn("user_content", turn)
            self.assertIn("final_response", turn)
            self.assertIn("intermediate_data", turn)

        eval_cfg = json.loads(eval_cfg_path.read_text(encoding="utf-8"))
        self.assertIn("criteria", eval_cfg)
        self.assertIn("tool_trajectory_avg_score", eval_cfg["criteria"])


if __name__ == "__main__":
    unittest.main()
