# Story S1-01: F-01 — Document Ingestion & Section-Reader Tools

## 1. Story Metadata & Sprint Mapping
- **Story ID**: `S1-01`
- **Use Case**: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor
- **Source Feature**: `F-01` (`CUJ 1`)
- **Priority / Phase**: `P0 (Phase 1 — Slice 1)` · **RICE Score**: `4800`
- **Upstream Contracts**: [`../PRD.md`](../PRD.md) · [`../TDD.md`](../TDD.md)

## 2. Single-Story Objective & Acceptance Criteria
- **Objective**: Scaffold `specalign-agent` with `agents-cli create` and implement deterministic Option A document ingestion (`ingest_document`) plus bounded heading-based reading (`list_doc_sections`, `read_doc_section`) for pasted Google Doc text, `.docx` (`python-docx`), `.md`, and `.txt` inputs.
- **Acceptance Criteria**:
  1. `app/tools/doc_tools.py` normalizes pasted text, `.docx` headings/tables, `.md`, and `.txt` into `session.state["ingested_docs"][doc_role]` (supporting `prd`, `tdd`, and optional `business_goals`).
  2. `read_doc_section` enforces a hard cap of `15` section reads per document and `4,000` characters per chunk, returning fuzzy heading suggestions or structured `recovery_guidance` on missing/malformed input (zero raw Python tracebacks).
  3. Protected acceptance test `tests/test_doc_tools.py` is written **before** implementation, passes completely via `uv run pytest tests/test_doc_tools.py -q`, and contains zero unresolved stubs.

## 3. Architectural & Tool Contract Slice (from `docs/TDD.md`)
- **Pillar 1 — BUILD**: Implement `ingest_document(doc_role, raw_text=None, file_path=None)`, `list_doc_sections(doc_role)`, and `read_doc_section(doc_role, section_heading)` in `app/tools/doc_tools.py` with comprehensive ADK docstrings and typed return dicts; preserve scaffolded `pyproject.toml` and add `python-docx` via `uv add`.
- **Pillar 2 — SCALE**: Store normalized section dictionaries in `session.state["ingested_docs"]` and read counters in `session.state["section_read_counts"]` to keep extraction prompts bounded.
- **Pillar 3 — GOVERN**: Reject unsupported file extensions and missing document roles with structured `INVALID_INPUT` / `MISSING_REQUIRED_DOCUMENT` error envelopes rather than raw exceptions.
- **Pillar 4 — OPTIMIZE**: Support reading local `.md` fixtures under `evals/fixtures/` directly so downstream golden dataset tests execute headlessly.

## 4. Target Implementation & Protected Test Paths
- **Implementation Module(s)**: `app/tools/doc_tools.py`, `app/agent.py` (Slice 1 baseline wiring)
- **Protected Acceptance Test(s)**: `tests/test_doc_tools.py`

## 5. Verification Commands
```bash
# Run Slice 1 protected unit tests
uv run pytest tests/test_doc_tools.py -q
```
