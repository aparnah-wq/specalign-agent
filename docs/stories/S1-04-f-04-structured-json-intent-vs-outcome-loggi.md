# Story S1-04: F-04 — Structured JSON Logging, Cloud Trace & 7-Case Golden Eval Suite

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S1-04`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-04` (`CUJ 2`)
- **Priority / Phase**: `P0 (Phase 1 — Slice 3)` · **RICE Score**: `2400`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Instrument every tool and agent transition with structured JSON intent-vs-outcome logging and OpenTelemetry tracing (`app/telemetry.py`), author the 7 clean-room synthetic PRD+TDD golden fixtures (`TC-01` through `TC-07`), and configure `adk eval` plus `agents-cli deploy` IaC documentation.
- **Acceptance Criteria**:
  1. `app/telemetry.py` emits structured JSON `tool_intent` (pre-execution) and `tool_outcome` (post-execution with `latency_ms` and `status`) events via Python `logging` with zero bare `print()` statements and zero unredacted PII.
  2. `evals/fixtures/` contains all 7 clean-room test suites (`tc01_clean` through `tc07_stale_prd_verbal`) and `evals/specalign_golden.test.json` passes `uv run adk eval` against all 4 quantitative release gates.
  3. Protected acceptance test `tests/test_telemetry.py` verifies JSON log formatting, intent/outcome correlation, and fixture completeness.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Wrap tool functions with a lightweight `@trace_tool_call` telemetry decorator in `app/telemetry.py`.
- **Pillar 2 — SCALE**: Keep synthetic fixtures concise (300–600 words per doc) so full 7-case `adk eval` runs complete in under 4 minutes within default Vertex AI RPM quotas.
- **Pillar 3 — GOVERN**: Confirm structured logs emit document hashes, section headings, and finding IDs only—never raw pasted document text or secrets.
- **Pillar 4 — OPTIMIZE**: Verify OpenTelemetry Cloud Trace span linkage on Agent Runtime (`agents-cli deploy --service-account specalign-agent-sa@... --region us-central1`) and document setup/cleanup (`?force=true`) in `README.md`.

## 4. Target Implementation & Protected Test Paths
- **Implementation Module(s)**: `app/telemetry.py`, `evals/specalign_golden.test.json`, `evals/fixtures/`, `README.md`
- **Protected Acceptance Test(s)**: `tests/test_telemetry.py`

## 5. Verification Commands
```bash
# Run telemetry unit tests and ADK golden evaluation suite
uv run pytest tests/test_telemetry.py -q
uv run adk eval app evals/specalign_golden.test.json --config_file_path evals/eval_config.json
```
