# Story S2-02: F-08 — Live External Issue Tracker (Jira / GitHub Issues) Writeback & Custom Web Frontend UI

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S2-02`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-08` (`CUJ 3`)
- **Priority / Phase**: `P1 (Phase 2 Backlog)` · **RICE Score**: `200`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Extend `record_alignment_decision` with optional HITL-gated writeback adapters for Jira and GitHub Issues, plus an optional web frontend consuming the deployed Agent Runtime endpoint.
- **Acceptance Criteria**:
  1. External issue creation strictly requires explicit human confirmation (`require_confirmation=True` + `human_confirmed=True`) and maps `action_owner` (`Engineering` vs. `PM / T/PgM`) to issue labels and assignees.
  2. API tokens are fetched exclusively via Google Cloud Secret Manager or delegated OAuth (zero hardcoded credentials).
  3. Protected acceptance tests validate mocked external writeback, retry/error-recovery envelopes, and zero regressions on Phase 1 tests.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Implement an `IssueTrackerAdapter` seam alongside `FirestoreAuditStore` so external writeback stays decoupled from core alignment reasoning.
- **Pillar 2 — SCALE**: Bound external API timeouts (`5s`) and retry transient HTTP 429/503 responses gracefully.
- **Pillar 3 — GOVERN**: Block autonomous external writes without HITL confirmation and redact PII before dispatching issue payloads.
- **Pillar 4 — OPTIMIZE**: Emit structured `tool_intent` and `tool_outcome` JSON logs and OpenTelemetry spans for every external API call.

## 4. Verification Commands (Phase 2)
```bash
uv run pytest -q
```
