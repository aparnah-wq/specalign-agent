# Story S1-05: F-05 — Mandatory HITL Sign-Off Gate & Gap-Ticket Persistence

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S1-05`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-05` (`CUJ 1`)
- **Priority / Phase**: `P0 (Phase 1 — Slice 2)` · **RICE Score**: `1600`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Implement persistent storage (`app/storage.py` supporting Cloud Firestore Native `(default)` and local SQLite offline mode) and the HITL-gated `record_alignment_decision` tool (`app/tools/audit_tools.py`) so no formal sign-off or gap ticket is persisted without explicit human approval.
- **Acceptance Criteria**:
  1. Calling `record_alignment_decision` without explicit human confirmation (`human_confirmed=True`) pauses and returns a structured confirmation request summarizing `blocker_count`, `prd_backfill_count`, and proposed ticket payloads without writing any database rows.
  2. Attempting to mark `decision_status="Approved"` while `blocker_count > 0` requires a non-empty `reviewer_note` risk waiver; otherwise it fails closed with actionable guidance.
  3. Protected acceptance test `tests/test_storage_hitl.py` passes via `uv run pytest tests/test_storage_hitl.py -q` against an isolated temporary SQLite database.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Implement `get_previous_audit` and `record_alignment_decision` in `app/tools/audit_tools.py` plus clean storage abstraction (`FirestoreAuditStore` / `SQLiteAuditStore`) in `app/storage.py`.
- **Pillar 2 — SCALE**: Use lazy cached `firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))` (using `project=`, never `project_id=`) with 5-second timeout and 2 retries.
- **Pillar 3 — GOVERN**: Enforce mandatory HITL approval checkpoint before any mutative database write; require `roles/datastore.user` on `specalign-agent-sa`.
- **Pillar 4 — OPTIMIZE**: Log structured pre-write `tool_intent` and post-write `tool_outcome` records carrying `project_key`, `decision_status`, and created ticket IDs.

## 4. Target Implementation & Protected Test Paths
- **Implementation Module(s)**: `app/storage.py`, `app/tools/audit_tools.py`
- **Protected Acceptance Test(s)**: `tests/test_storage_hitl.py`

## 5. Verification Commands
```bash
# Run HITL gate and persistence unit tests
uv run pytest tests/test_storage_hitl.py -q
```
