# Story S2-01: F-07 — Live Google Docs / GitHub PR Webhook & BYO-MCP Connector for Proactive Drift Audits

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S2-01`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-07` (`CUJ 3`)
- **Priority / Phase**: `P1 (Phase 2 Backlog)` · **RICE Score**: `480`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Plug an admin-allowlisted BYO-MCP Connector (Google Docs / GitHub PR webhook via Cloud Pub/Sub) into SpecAlign's existing `ingest_document` seam so PR updates touching `docs/TDD.md` trigger proactive read-only drift checks without modifying the 4 core reasoning agents.
- **Acceptance Criteria**:
  1. Event-driven Cloud Pub/Sub handler fetches linked PRD and TDD revisions through a delegated OAuth / MCP tool and feeds normalized text directly into `ingest_document`.
  2. Untrusted PR/Doc inputs pass `before_model_guardrail_callback` (PII redaction and prompt-injection defense) and never bypass HITL for formal sign-off.
  3. Protected acceptance tests verify read-only PR annotation and zero regressions on the Phase 1 7-case golden evaluation suite.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Add a Phase 2 `fetch_google_doc` / `fetch_github_pr_doc` MCP tool behind the Phase 1 `ingest_document` interface.
- **Pillar 2 — SCALE**: Enforce bounded per-turn fan-out, async timeouts, and 5x Vertex AI RPM/TPM headroom.
- **Pillar 3 — GOVERN**: Load OAuth secrets strictly from Google Cloud Secret Manager and preserve human-in-the-loop sign-off gates.
- **Pillar 4 — OPTIMIZE**: Preserve Phase 1 Golden Dataset thresholds (`>= 90%` Blocker recall, `>= 80%` root-cause accuracy, `0%` PII leaks).

## 4. Verification Commands (Phase 2)
```bash
uv run pytest -q
uv run adk eval app evals/specalign_golden.test.json --config_file_path evals/eval_config.json
```
