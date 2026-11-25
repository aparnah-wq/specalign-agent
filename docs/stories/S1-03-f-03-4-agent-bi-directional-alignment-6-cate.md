# Story S1-03: F-03 — 4-Agent Bi-Directional Alignment & 6-Category Root-Cause Analyzer

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S1-03`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-03` (`CUJ 1`)
- **Priority / Phase**: `P0 (Phase 1 — Slice 2)` · **RICE Score**: `2880`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Build the Pydantic v2 domain models (`app/schemas.py`) and 4-agent ADK topology (`SequentialAgent` wrapping `ParallelAgent` [`prd_goal_extractor`, `tdd_architecture_extractor` on `gemini-2.5-flash`] -> `alignment_analyzer` on `gemini-2.5-pro` -> `review_action_agent` on `gemini-2.5-flash`) with 6-category drift root-cause classification and verbatim citation verification.
- **Acceptance Criteria**:
  1. `app/schemas.py` defines strict Pydantic v2 models (`AlignmentStatus`, `Severity`, `RootCauseCategory` with all 6 variance enums including `STALE_OR_MISSING_PRD_SPEC`, `AlignmentFinding`, and `AlignmentReport`) with explicit `action_owner` (`Engineering`, `PM`, `PM / T/PgM`, `Shared`).
  2. `app/agent.py` routes extraction and formatting to `gemini-2.5-flash` and cross-document reasoning to `gemini-2.5-pro` with `HttpRetryOptions(attempts=3)`, separating **Engineering TDD Fixes** from **PM & T/PgM PRD Backfills**.
  3. Protected acceptance test `tests/test_schemas_and_topology.py` validates schema constraints, citation grounding verification, and ADK agent graph wiring (`ParallelAgent` -> `SequentialAgent`).

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Implement constitution system prompts for `prd_goal_extractor`, `tdd_architecture_extractor` (extracting `documented_tradeoffs` and `unstated_business_rules_and_sync_notes`), `alignment_analyzer`, and `review_action_agent`.
- **Pillar 2 — SCALE**: Read/write structured extracts strictly through typed `session.state` keys (`prd_extract`, `tdd_extract`, `alignment_report`) so `gemini-2.5-pro` processes compact JSON rather than raw 40-page text.
- **Pillar 3 — GOVERN**: Enforce deterministic citation verification confirming every non-empty `prd_quote` / `tdd_quote` exists verbatim in the ingested source text.
- **Pillar 4 — OPTIMIZE**: Hit `>= 90%` Blocker recall, `<= 10%` false-positive Blocker rate, `>= 80%` 6-category root-cause accuracy, and `>= 95%` citation grounding on the 7-case golden set.

## 4. Target Implementation & Protected Test Paths
- **Implementation Module(s)**: `app/schemas.py`, `app/agent.py`
- **Protected Acceptance Test(s)**: `tests/test_schemas_and_topology.py`

## 5. Verification Commands
```bash
# Run schema, grounding & multi-agent topology tests
uv run pytest tests/test_schemas_and_topology.py -q
```
