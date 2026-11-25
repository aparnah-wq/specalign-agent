# Story S1-06: F-06 — Stateful Revision Delta Tracking via Sessions & Async Memory Bank

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S1-06`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-06` (`CUJ 2`)
- **Priority / Phase**: `P0 (Phase 1 — Slice 3)` · **RICE Score**: `1280`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Wire cross-session memory extraction (`after_agent_callback=[add_session_to_memory_callback]`), automatic recall (`PreloadMemoryTool()`), and structured revision-over-revision diffing (`v1 -> v2`) so a fresh session immediately recalls prior blockers and PRD backfills without repeating context.
- **Acceptance Criteria**:
  1. `add_session_to_memory_callback` runs asynchronously via `await callback_context.add_session_to_memory()` and gracefully handles `ValueError` in local in-memory playground runs without blocking or raising.
  2. `PreloadMemoryTool()` is attached to `review_action_agent` / root coordinator and `get_previous_audit(project_key)` hydrates `session.state["previous_audit"]` so `AlignmentReport.delta_from_previous` accurately lists closed blockers, remaining gaps, and newly introduced regressions between v1 and v2.
  3. Protected acceptance test `tests/test_revision_memory.py` passes via `uv run pytest tests/test_revision_memory.py -q`.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Attach `PreloadMemoryTool()` to `tools=[...]` and `after_agent_callback=[add_session_to_memory_callback]` in `app/agent.py` following Workshop Lab Part 3 write+recall wiring.
- **Pillar 2 — SCALE**: Use `VertexAiSessionService` and `VertexAiMemoryBankService` (90-day TTL) automatically on Agent Runtime, backed by Firestore/SQLite revision baselines.
- **Pillar 3 — GOVERN**: Ensure PII redaction runs prior to session persistence so zero sensitive tokens enter Agent Memory Bank.
- **Pillar 4 — OPTIMIZE**: Validate live cross-session recall in Cloud Console Playground (Session 1 v1 audit -> wait 30–60s -> verify Memories tab -> Session 2 v2 delta audit).

## 4. Target Implementation & Protected Test Paths
- **Implementation Module(s)**: `app/callbacks.py`, `app/agent.py`, `app/tools/audit_tools.py`
- **Protected Acceptance Test(s)**: `tests/test_revision_memory.py`

## 5. Verification Commands
```bash
# Run revision delta & async memory callback tests
uv run pytest tests/test_revision_memory.py -q
```
