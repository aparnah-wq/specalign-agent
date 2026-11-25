# PRD: SpecAlign — Multi-Agent PRD-to-TDD Alignment Auditor

| SpecAlign Multi-Agent Auditor PRD | | **Summary:** A 4-agent ADK solution that compares Product Requirements, Business Goals/OKRs, and Technical Design Documents to flag missing coverage, contradictions, scope creep, and probable drift causes before engineering sprints lock in. |
| :--- | :--- | :--- |
| **Authors:** SpecAlign Author (Product & Technical Owner)<br>**Reviewers:** Capstone Technical Reviewer | **Status:** Final (Phase 1 MVP)<br>**Last Revised:** 2026-11-25<br>**Read Time:** ~6 min | **Context & Upstream Artifacts:**<br>- AI in 5 Days (L200) Enterprise Agents Capstone (95-Point AgentOps Rubric)<br>- Target Delivery Track: Enterprise Agents (Clean-Room Public Repository) |

**Discovery & Alignment Inputs:**
- 2026-11-21: Capstone Idea Scoping & Guardrail Lock (Phase 1 Zero-OAuth MVP + Root-Cause Drift Analysis + Golden Dataset Eval)
- 2026-11-21: Gate 1 PRD Revision 1 (Added AI Activation Lead / T/PgM persona and `STALE_OR_MISSING_PRD_SPEC` verbal-decision gap detection)
- 2026-11-21: Gate 1 PRD Revision 2 (Locked Option A Input UX: pasted Google Doc text or `.docx`/`.md`/`.txt` chat upload in Phase 1; live Google Doc URL OAuth in Phase 2)

---

## 1. USE CASE

Every quarter, Technical Deployment Leads (TDLs), AI Activation Leads, Technical Program Managers (T/PgMs), Product Managers, and Tech Leads spend 3 to 5 hours per design review manually cross-reading a 15-page PRD, an executive OKR brief, and a 25-page TDD sent as Google Doc links across separate tabs before engineering kickoff. High-severity alignment failures still slip into Sprint 3: a hard EU data-residency requirement gets dropped in a `us-central1` deployment diagram, a sub-2-second latency goal conflicts with a proposed batch pipeline, an engineer adds a custom Kafka cluster with zero backing business requirement, or missing PRD details get decided verbally in meetings and written straight into the TDD without anyone updating the PRD. Reworking an architecture mid-build burns 1 to 2 engineering weeks per missed constraint, breaks alignment for QA and governance reviewers, and erodes executive trust when the shipped system fails to move the original business KPI.

Our bet for Phase 1 reflects real team habits while keeping implementation clean and deterministic. Although teams normally share Google Doc links, enterprise Workspace OAuth restrictions often block unverified sandbox OAuth apps from reading organization Google Docs without IT admin allowlisting. Rather than asking teammates to trade `.md` files or stalling for weeks on OAuth plumbing, Phase 1 accepts **pasted Google Doc text** (*Edit → Copy as Markdown* or copy-paste) or **1-click uploaded `.docx` / `.md` / `.txt` exports** directly inside the ADK Playground UI (while keeping local `.md` fixtures strictly for automated evals). SpecAlign runs a 4-agent `ParallelAgent` + `SequentialAgent` pipeline on Google Cloud Agent Runtime, produces a cited bi-directional Traceability Matrix with 6-category root-cause classification, pauses at a Human-in-the-Loop (HITL) gate before saving sign-off or gap tickets, and remembers open gaps across revisions via Firestore and Agent Memory Bank.

### Primary Objective

SpecAlign serves product, program, architecture, and delivery leads across software and AI engagement teams by replacing manual side-by-side document diffing with an evidence-backed multi-agent alignment audit and stateful revision tracker.

| Dimension | Specification |
| :--- | :--- |
| **Title** | Audit PRD, Business Goals, and TDD Alignment Before Design Sign-Off |
| **Persona Identification** | "As a Technical Deployment Lead (TDL), AI Activation Lead / Technical Program Manager (T/PgM), Product Manager, or Engineering Tech Lead preparing for a design review gate" |
| **Context Trigger** | When a new or revised TDD is shared for review against an approved PRD and optional Business Goals / OKR Charter, and I paste or upload both documents into SpecAlign (with direct Google Doc URL ingestion planned for Phase 2). |
| **The Goal** | I need an automated multi-agent audit that extracts all goals and requirements, flags missing coverage, contradictions, scope creep, and stale/missing PRD details filled in from verbal discussions with verbatim section citations, infers why each variance occurred, and tracks whether revision v2 closed prior blockers. |
| **Strategic Outcome** | So that I cut manual pre-review prep time by 60% (from ~4 hours to under 90 minutes), catch >= 90% of P0 requirement/NFR gaps before Sprint 1 coding starts, keep PRDs synchronized as the single source of truth, and gate every formal sign-off behind explicit human approval. |

### Target User Personas

| Persona | Core Responsibility | Trigger & Frequency | Primary Pain Today | What Success Looks Like in SpecAlign |
| :--- | :--- | :--- | :--- | :--- |
| **Technical Deployment Lead (TDL) / Solutions Architect** *(Primary)* | Bridges customer business outcomes with technical architecture across delivery gates. | Runs 2 to 4 PRD-to-TDD gate reviews per quarter per squad. | Spends half a day reading two linked Google Docs side by side to verify whether every KPI, SLA, and compliance guardrail survived into the TDD. | Pastes or uploads the PRD, Business Goals, and TDD (`.docx`/`.md`/text) directly in chat; gets a cited Traceability Matrix in under 45 seconds and tracks blocker closure from v1 to v2. |
| **AI Activation Lead / Technical Program Manager (T/PgM)** *(Primary)* | Drives cross-functional delivery readiness, phase-gate governance, dependency tracking, and program RAID logs across product, engineering, and business stakeholders. | Runs readiness gates across 3 to 5 workstreams per quarter and audits design drift whenever scope or milestone risks surface. | Chases PMs and Tech Leads across meetings and chat threads to uncover uncaptured verbal decisions, stale PRDs, and hidden compliance or schedule risks. | Receives one concise Alignment Scorecard tagging Blocker risks, PRD backfill items, and clear PM vs. Engineering owners ready to drop directly into the program RAID log. |
| **Product Manager (PM)** | Owns business KPIs, prioritized requirements (Must-Have vs. Nice-to-Have), and scope boundaries. | Reviews TDD before sprint lock and whenever scope changes mid-engagement. | Cannot always decode deep infrastructure sections to spot silent requirement drops, unjustified gold-plating, or places where engineering filled in missing PRD specs from meetings. | Sees plain-language findings separating accidental TDD omissions from documented trade-offs and stale/ambiguous PRD sections that need a quick PRD update. |
| **Engineering Tech Lead / EM** | Authors the TDD, owns technical trade-offs, cost, reliability, and delivery timeline. | Pre-flights own TDD draft before architecture review board. | Wastes review meetings defending valid platform trade-offs or explaining decisions made in side conversations because the PRD left details out. | Runs a pre-flight self-check before circulating the TDD, surfacing vague/missing PRD specs (`AMBIGUOUS_PRD_SPEC` / `STALE_OR_MISSING_PRD_SPEC`) and confirming intentional trade-offs are documented. |
| **Executive Sponsor / Capstone Reviewer** *(Secondary)* | Signs off on phase-gate readiness, business alignment, and risk posture. | Reviews final gate scorecard prior to launch or certification approval. | Gets buried in raw 40-page docs without a concise alignment score or clear blocker summary. | Reads a 1-page Alignment Scorecard showing Blocker count, business-goal coverage percentage, and audited human sign-off timestamp. |

### Strategic Opportunity Analysis

* **Eliminate Late-Stage Architecture Rework:** Catching a single missed compliance constraint (such as regional residency or PII redaction) during design review avoids 40 to 80 engineering hours of mid-sprint refactoring.
* **Distinguish Valid Trade-Offs and Stale PRDs from Silent Bugs:** Standard diff tools only flag that two docs disagree. Classifying each variance into six root causes (Intentional Trade-Off, Accidental Omission, Undocumented Contradiction, Unjustified Scope Creep, Ambiguous PRD, or Stale/Missing PRD Built from Verbal Decisions) tells PMs, T/PgMs, and Tech Leads whether to fix the TDD or backfill the PRD.
* **Persistent Cross-Revision Memory:** Storing audit baselines in Firestore and ADK Memory Bank removes the repetitive work of re-checking whether TDD v2 actually fixed the 3 Blockers raised against TDD v1.
* **Clean Upgrade Path to Direct Google Doc Links (Phase 2):** Normalizing pasted text and `.docx`/`.md` uploads behind narrow ADK section-reader tools keeps Phase 1 completely free of OAuth policy walls, while letting Phase 2 plug in an admin-approved Google Docs OAuth / Workspace MCP connector so users simply paste two Doc URLs with zero rewrite to the 4 reasoning agents.

---

## 2. PAIN POINTS & PROBLEMS

Addressing these adoption-preventing blockers and efficiency-draining friction points governs every architecture choice in Phase 1.

| Classification | Pain Point | Description & Operational Impact |
| :--- | :--- | :--- |
| **Blocker (Adoption-Preventing)** | Silent Business Goal & NFR Drift | Non-functional constraints (latency caps, PII scrubbing, EU residency, cost ceilings) written in PRDs or OKR charters routinely vanish from TDDs. Teams discover the gap only during security review or load testing, halting launch. |
| **Blocker (Adoption-Preventing)** | Unverifiable LLM Hallucinations in Doc Reviews | Reviewers abandon generic "paste both docs into a chat window" prompts after a single fabricated gap wastes 20 minutes of meeting time. Without strict Pydantic schemas and exact section quotes, trust drops to zero. |
| **Blocker (Adoption-Preventing)** | Enterprise Drive OAuth Policy Wall on Direct Doc Links | Teams naturally share Google Doc links, but enterprise domain OAuth policies often block unverified sandbox OAuth apps from requesting `drive.readonly` on organization Docs. Phase 1 bridges this with direct chat paste and `.docx`/`.md` upload until admin-allowlisted OAuth / Workspace MCP connectors land in Phase 2. |
| **Friction (Efficiency-Draining)** | Manual Cross-Document Tab Switching | PMs, T/PgMs, and TDLs spend 3 to 5 hours per review reading 30 to 50 combined pages of linked Google Docs to build an ad-hoc traceability checklist in a spreadsheet. |
| **Friction (Efficiency-Draining)** | Repeated Re-Audits Across TDD Revisions | When engineers publish revision v2 of a TDD, reviewers re-read the entire document from scratch because prior feedback lives in scattered comment threads with no structured delta view. |
| **Friction (Efficiency-Draining)** | Stale / Vague PRDs Filled From Verbal Decisions | When PRDs leave workflows vague or omit edge-case rules, engineers clarify requirements in Slack or standups and bake decisions straight into the TDD without updating the PRD. T/PgMs, QA, and downstream teams then operate from an outdated spec, while reviewers risk mislabeling agreed features as scope creep. |

---

## 3. CRITICAL USER JOURNEYS (CUJs)

Phase 1 focuses exclusively on reactive, user-initiated reviews executed via `agents-cli playground` (`adk web`) or the Agent Runtime Console Playground using pasted doc text or `.docx`/`.md`/`.txt` uploads. Phase 2 adds direct Google Doc URL ingestion and proactive, event-driven triggers.

### CUJ 1: Initial PRD + Business Goals vs. TDD Alignment Audit & HITL Sign-Off (Phase 1 — Reactive)

| Step | Phase | Action Details |
| :--- | :--- | :--- |
| **1** | Trigger | User opens `agents-cli playground` (or Agent Runtime Playground) and pastes the PRD, TDD, and optional Business Goals text directly into chat (copied from Google Docs via *Edit → Copy as Markdown* or `Cmd+A/C`) or attaches 1-click `.docx` / `.md` / `.txt` exports. |
| **2** | Input Normalization & PII Guardrail | `ingest_document` normalizes pasted text or `.docx`/`.md`/`.txt` uploads into structured heading-indexed sections. `before_model_callback` scans content for sensitive PII (emails, phone numbers, SSNs, API keys), redacts matches before logging or model invocation, and verifies both a PRD and TDD were supplied (returning actionable recovery tips if either is missing or unreadable). |
| **3** | Parallel Extraction | `ParallelAgent` launches `PRDGoalExtractor` and `TDDArchitectureExtractor` simultaneously on `gemini-2.5-flash`. Each sub-agent calls `list_doc_sections` and `read_doc_section` to extract structured JSON lists of requirements, KPIs, NFRs, architecture components, constraints, and documented trade-offs. |
| **4** | Deep Alignment & Root-Cause Analysis | `AlignmentAnalyzer` (running on `gemini-2.5-pro`) compares both structured extracts bi-directionally (PRD/OKRs to TDD and TDD to PRD), emits a Pydantic-validated Traceability Matrix classifying each item (`Aligned`, `Partially Covered`, `Missing`, `Contradiction`, `Scope Creep`, `PRD Backfill Required`), assigns severity (`Blocker`, `High`, `Medium`, `Low`), infers one of six drift root causes (including missing or vague PRD specs filled in from verbal discussions), and attaches exact section quotes from both files. |
| **5** | Action Proposal & Mandatory HITL Gate | `ReviewActionAgent` (`gemini-2.5-flash`) formats the executive Alignment Scorecard (splitting actions cleanly into **TDD Fixes** for Engineering vs. **PRD Backfills** for PM and AI Activation Lead / T/PgM) and drafts follow-up actions. Before calling `record_alignment_decision`, the agent pauses at a mandatory Human-in-the-Loop confirmation gate, displaying any open `Blocker` counts for explicit user approval. |
| **6** | Persistent Record & Async Memory | Upon human confirmation, the tool persists the audit scorecard and gap tickets to Firestore/SQLite, and `after_agent_callback` asynchronously commits distilled session facts to ADK Memory Bank without blocking the user response. |

### CUJ 2: Revision Re-Audit & Cross-Session Delta Tracking (Phase 1 — Reactive)

| Step | Phase | Action Details |
| :--- | :--- | :--- |
| **7** | Context Hydration | In a brand-new session days later, the user pastes or uploads the revised TDD (`tdd_v2`) or updated PRD (`prd_v2`) for the same project. `PreloadMemoryTool()` queries ADK Memory Bank while `get_previous_audit` loads the last saved baseline from Firestore/SQLite. |
| **8** | Targeted Re-Audit | The 4-agent pipeline evaluates the updated docs against the business goals charter and computes a structured diff against the v1 baseline, checking both TDD fixes and PM PRD backfills. |
| **9** | Interactive Drill-Down | User asks follow-up questions in conversation (for example, *"Why did you flag the refund retry rule as a Stale PRD Spec instead of Scope Creep?"*). The agent answers directly from cited TDD text without re-reading whole files. |
| **10** | Delta Sign-Off | Agent summarizes closed gaps, remaining blockers, and any newly introduced regressions, then pauses at the HITL gate before updating the project's sign-off status to `Approved` or `Changes Requested`. |

### Transition to Proactive Design-Gate Automation

### CUJ 3: Automated Pull-Request / Doc-Revision Drift Check (Phase 2 — Proactive)

| Step | Phase | Action Details |
| :--- | :--- | :--- |
| **11** | Event Trigger | A GitHub PR touching `docs/TDD.md` or a Google Docs revision webhook fires a Cloud Pub/Sub event without manual chat invocation. |
| **12** | Autonomous Extraction | SpecAlign fetches the linked PRD, OKR brief, and updated TDD via a BYO-MCP Server Node (Google Docs / GitHub MCP) and runs the 4-agent alignment pipeline. |
| **13** | Automated Check Annotation | If 0 Blockers are found, the agent posts a read-only pass summary comment to the PR or Doc. If `>= 1` Blocker or `STALE_OR_MISSING_PRD_SPEC` gap exists, it posts a draft checklist and flags the PM, Tech Lead, and AI Activation Lead / T/PgM. |
| **14** | Human Escalation & Audit Trail | Formal approval overrides or external Jira/GitHub Issues ticket creation remain gated behind explicit human confirmation, with full OpenTelemetry traces logged to Cloud Trace. |

---

## 4. INFORMATION ARCHITECTURE & DAG DESIGN

SpecAlign uses a hybrid `ParallelAgent` + `SequentialAgent` topology in ADK-Python. Narrow local connectors keep Phase 1 simple and deterministic while preserving clean seams for Phase 2 enterprise connectors and MCP servers.

| Architecture Component | Type | Details & Functionality |
| :--- | :--- | :--- |
| **Triggers** | Manual *(Phase 1)* | User-initiated audit and follow-up dialogue via `agents-cli playground` (`adk web`) or Agent Runtime Console Playground. |
| | Scheduled *(Phase 2)* | Weekly cron sweep comparing active project PRDs against living TDDs to surface silent mid-sprint drift. |
| | Event-Driven *(Phase 2)* | GitHub Pull Request or Google Drive revision webhook over Cloud Pub/Sub triggering automated pre-review checks. |
| **Nodes** | Connectors *(Phase 1 Local / Phase 2 Enterprise)* | Phase 1: Deterministic document ingestion & section-reader tools (`ingest_document`, `list_doc_sections`, `read_doc_section`) accepting pasted Google Doc text or `.docx` (via `python-docx`), `.md`, and `.txt` chat uploads (plus local `.md` fixtures for automated `adk eval`), paired with Firestore/SQLite audit-store tools (`get_previous_audit`, `record_alignment_decision`). Phase 2: Admin-allowlisted 3-legged OAuth Google Docs URL fetcher, GitHub, and Jira/GitHub Issues enterprise connectors. |
| | Section-Indexed Retrieval / RAG Node | Heading-based section index (`list_doc_sections` + `read_doc_section`) lets extractors fetch targeted sections from normalized pasted/uploaded docs instead of stuffing 50-page raw text into context, preventing token bloat. Phase 2 extends to partitioned Vertex AI Search RAG across historical ADRs and org standards. |
| | BYO-MCP Server Node *(Phase 2)* | Clean Model Context Protocol interface reserved for Phase 2 integration with live Google Drive/Docs, GitHub, and internal ticketing systems without modifying core agent logic. |
| | Multi-Agent Orchestrator *(Phase 1)* | Root `SequentialAgent` (`SpecAlignOrchestrator`) coordinating: (1) `ParallelAgent` running `PRDGoalExtractor` + `TDDArchitectureExtractor` (`gemini-2.5-flash`), (2) `AlignmentAnalyzer` (`gemini-2.5-pro`), and (3) `ReviewActionAgent` (`gemini-2.5-flash`). |
| **Logic Gates** | Conditional Branching | Deterministic input gate checks file presence and schema validity before calling the Pro judge; severity gate separates `Clean Pass` (0 Blockers) from `Action Required` (`>= 1` Blocker or Contradiction), routes `INTENTIONAL_TRADEOFF` items to PM review, and routes `STALE_OR_MISSING_PRD_SPEC` and `AMBIGUOUS_PRD_SPEC` items to a dedicated PM / T/PgM PRD-Backfill queue rather than defect queues. |
| | Looping | Bounded section-reading loop (max 15 section reads per document) with context compaction so large PRDs/TDDs never exceed token limits or enter infinite tool loops. |
| | Human-in-the-Loop (HITL) | Mandatory `RequestInput` / tool-confirmation checkpoint before `record_alignment_decision` persists a formal sign-off state or writes gap tickets to Firestore/SQLite, displaying exact Blocker counts and proposed ticket summaries for explicit human approval. |

### Drift Root-Cause Taxonomy (Answering *Why* the TDD Varied)

To go beyond surface-level "mismatch" alerts, `AlignmentAnalyzer` enforces a strict Pydantic enum (`root_cause_category`) on every non-aligned finding by cross-checking the TDD's Trade-Offs, Constraints, Assumptions, Meeting/Decision Notes, and Risks sections:

| Root-Cause Category | Meaning | Evidence & Signal Cues Required from Docs | Recommended Next Step |
| :--- | :--- | :--- | :--- |
| **`INTENTIONAL_TRADEOFF`** | Engineer explicitly chose a different design due to cost, quota, latency, or platform constraint and documented the rationale. | Quote of PRD target + quote of TDD trade-off/decision rationale. | Route to PM to confirm trade-off and update PRD (not a coding bug). |
| **`ACCIDENTAL_OMISSION`** | PRD requirement or Business Goal is completely absent from the TDD with no explanation. | Quote of PRD requirement + list of inspected TDD sections showing zero coverage. | Add technical design section to TDD before sign-off. |
| **`UNDOCUMENTED_CONTRADICTION`** | TDD architecture directly violates a PRD constraint (e.g., region, encryption, SLA) without acknowledging the conflict. | Side-by-side conflicting quotes from PRD and TDD. | Flag as **Blocker**; halt sign-off until reconciled. |
| **`UNJUSTIFIED_SCOPE_CREEP`** | TDD introduces major infrastructure, dependencies, or features with no backing PRD requirement, business goal, or stakeholder agreement. | Quote of TDD component + confirmation of zero matching PRD/OKR item or stakeholder decision cue. | Challenge unnecessary complexity in design review to protect schedule and cost. |
| **`AMBIGUOUS_PRD_SPEC`** | PRD mentions a requirement but lacks measurable criteria (e.g., "must be fast and scalable"), forcing the TDD author to guess concrete thresholds. | Quote of vague PRD sentence + concrete numeric assumption made in TDD. | Ask PM to quantify measurable acceptance criteria in the PRD. |
| **`STALE_OR_MISSING_PRD_SPEC`** | PRD omitted functional rules, edge cases, or workflows entirely, and engineering built them into the TDD based on verbal conversations, syncs, or offline stakeholder decisions instead of updating the PRD. | Quote of concrete business rule/workflow in TDD (often carrying cues like *"per sync"*, *"agreed with ops"*, *"confirmed offline"*, or explicit business thresholds) + confirmation of zero matching PRD section. | Route to PM and AI Activation Lead / T/PgM to ratify and backfill the PRD so QA, governance, and future teams share one source of truth. |

---

## 5. PRIORITIZED REQUIREMENTS, RICE BACKLOG & PLATFORM LAUNCH ALIGNMENT

### 5.1 Platform Dependency & GA Alignment

All Phase 1 capabilities rely strictly on standard Google Cloud Agent Runtime and ADK-Python 2.x capabilities to guarantee smooth execution in Google Cloud Shell or Linux.

| Platform Capability / Feature | Priority | Target / GA Date |
| :--- | :--- | :--- |
| **ADK-Python 2.x + `google-agents-cli`** (`ParallelAgent`, `SequentialAgent`, callbacks, `adk eval`) | P0 | Available (GA / Workshop Standard) |
| **Gemini 2.5 Flash & Gemini 2.5 Pro on Vertex AI** (Strategic model routing for extraction vs. deep reasoning) | P0 | Available (GA on Vertex AI) |
| **Agent Runtime, Sessions & Memory Bank** (Managed deployment via `agents-cli deploy`, `PreloadMemoryTool`, `after_agent_callback`) | P0 | Available (Workshop Lab Part 3 Stack) |
| **Cloud Firestore (Native Mode) & Cloud Trace / OpenTelemetry** (Audit baseline persistence, distributed tracing, structured JSON logs) | P0 | Available (GA) |
| **BYO-MCP Connectors (Google Docs, GitHub, Jira)** (Live enterprise document sync and PR webhook triggers) | P1 | Phase 2 Fast-Follow (Post-L200 Capstone) |

### 5.2 RICE-Prioritized Feature Backlog

$$\text{RICE Score} = \frac{\text{Reach} \times \text{Impact} \times \text{Confidence}}{\text{Effort (Person-Months)}}$$

*Estimation basis: Reach = estimated design reviews per quarter across a 30-squad engineering org; Impact = `3.0` massive, `2.0` high, `1.0` medium; Confidence = `1.0` proven in workshop labs, `0.8` benchmarked pattern, `0.5` Phase 2 hypothesis; Effort = 1 builder using ADK + AI coding assistant (`0.05 PM` ≈ 1 working day, `0.10 PM` ≈ 2 working days).*

| Feature ID | Feature Name | CUJ | Reach (/qtr) | Impact | Confidence | Effort (PM) | RICE Score | Priority / Phase |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **F-01** | Document Ingestion & Section-Reader Tools (`ingest_document`, `list_doc_sections`, `read_doc_section` for pasted text and `.docx`/`.md`/`.txt` uploads) with Guided Error Recovery | CUJ 1 | 120 | 2.0 | 1.0 | 0.05 | 4800 | P0 (Phase 1 — Slice 1) |
| **F-02** | Pre-Model PII Redaction & Missing-Input Guardrail Callbacks (`before_model_callback`) | CUJ 1 | 120 | 2.0 | 1.0 | 0.05 | 4800 | P0 (Phase 1 — Slice 3) |
| **F-03** | 4-Agent Bi-Directional Alignment & 6-Category Root-Cause Analyzer (Flash Extractors + Pro Judge + Pydantic Traceability Matrix) | CUJ 1 | 120 | 3.0 | 0.8 | 0.10 | 2880 | P0 (Phase 1 — Slice 2) |
| **F-04** | Structured JSON Intent-vs-Outcome Logging, OpenTelemetry Cloud Trace & 7-Case Planted-Defect Golden Eval Suite (`adk eval`) | CUJ 2 | 120 | 2.0 | 1.0 | 0.10 | 2400 | P0 (Phase 1 — Slice 3) |
| **F-05** | Mandatory HITL Sign-Off Gate & Gap-Ticket Persistence Tool (Firestore / SQLite) | CUJ 1 | 100 | 2.0 | 0.8 | 0.10 | 1600 | P0 (Phase 1 — Slice 2) |
| **F-06** | Stateful Revision-to-Revision Delta Tracking via Agent Sessions & Async Memory Bank (`after_agent_callback` + `PreloadMemoryTool`) | CUJ 2 | 80 | 2.0 | 0.8 | 0.10 | 1280 | P0 (Phase 1 — Slice 3) |
| **F-07** | Live Google Docs / GitHub PR Webhook & BYO-MCP Connector for Proactive Drift Audits | CUJ 3 | 120 | 2.0 | 0.5 | 0.25 | 480 | P1 (Phase 2) |
| **F-08** | Live External Issue Tracker (Jira / GitHub Issues) Writeback & Custom Web Frontend UI | CUJ 3 | 100 | 1.0 | 0.5 | 0.25 | 200 | P1 (Phase 2) |

### 5.3 Detailed Feature Acceptance Criteria & Non-Functional SLAs

- **Latency SLA:** `p95 <= 15s` for parallel section extraction on documents up to 5,000 words each; `p95 <= 45s` end-to-end for full 4-agent bi-directional alignment report.
- **Data Privacy & Security:** Zero hardcoded API keys or credentials (ADC / `.env` gitignored); least-privilege dedicated service account (`specalign-agent-sa`) on Agent Runtime with `roles/aiplatform.user`, `roles/datastore.user`, `roles/logging.logWriter`, and `roles/cloudtrace.agent`; `before_model_callback` redacts email addresses, credit card numbers, phone numbers, SSNs, and bearer/API tokens prior to model calls, logs, and Memory Bank persistence (0% PII leak rate).
- **Schema & Grounding Contract:** 100% of `AlignmentReport` responses conform to Pydantic schemas with explicit `requirement_id`, `alignment_status`, `severity`, `root_cause_category`, `action_owner` (`PM`, `Engineering`, `T/PgM`), `prd_quote`, and `tdd_quote` fields.
- **Observability Contract:** Every tool call emits structured JSON logs capturing pre-execution intent (`tool_name`, sanitized arguments, target document) and post-execution outcome (`status`, `latency_ms`, `finding_count`) linked to OpenTelemetry / Cloud Trace spans.
- **Clean-Room Public Repository Hygiene:** Repository stays 100% clean-room (synthetic sample PRDs/TDDs only, zero internal URLs, secrets, or proprietary data, root-level repo layout) for reproducible evaluation against the 95-Point AgentOps Rubric.

### 5.4 Testing & Evaluation Strategy

Testing operates across four layers to verify deterministic tool safety, defect detection accuracy, root-cause ("why") accuracy, and end-to-end agent behavior:

1. **Layer 1 — Deterministic Unit & Contract Tests (`pytest`):**
   - Validates document normalizer and heading parser (`ingest_document`, `list_doc_sections`, `read_doc_section`) across pasted plain text, `.docx` exports (`python-docx`), Markdown files, malformed headers, empty inputs, and missing paths (confirming actionable recovery messages rather than uncaught exceptions).
   - Validates Pydantic schema enforcement on valid and invalid `AlignmentReport` payloads.
   - Verifies PII redaction callback strips synthetic emails, SSNs, phone numbers, and API keys from both prompts and structured logs.
   - Verifies Firestore/SQLite persistence and revision lookup (`get_previous_audit`).
2. **Layer 2 — 7-Case "Planted-Defect" Golden Dataset Evaluation (`adk eval` / `.test.json`):**
   - Seven compact, synthetic PRD + Business Goals + TDD pairs (each 300 to 600 words) with ground-truth labeled variances test both *whether* the agent detects drift and *whether* it classifies **why** the variance occurred:

| Test Case ID | Synthetic Scenario | Planted Variance | Expected Classification & Gate Assertion |
| :--- | :--- | :--- | :--- |
| **TC-01** | Clean Payment API Spec | Zero defects; all PRD KPIs, SLAs, and constraints covered in TDD. | Alignment Score `>= 95%`; `0` Blockers; `0` false-positive Contradictions. |
| **TC-02** | Dropped Compliance & SLA | PRD mandates `p95 <= 2s` and audit logging; TDD omits both completely. | Flags 2 `Missing` (`Blocker`) items with `root_cause_category = ACCIDENTAL_OMISSION`. |
| **TC-03** | Regional Residency Conflict | Business Charter mandates EU-only data storage; TDD deploys Firestore in `us-central1` without noting the conflict. | Flags `Contradiction` (`Blocker`) with `root_cause_category = UNDOCUMENTED_CONTRADICTION` and verbatim quotes from both docs. |
| **TC-04** | Documented Platform Trade-Off | PRD asks for real-time sync updates; TDD explicitly documents an async Pub/Sub queue due to downstream 10 QPS quota limit and requests PM review. | Flags `Partially Covered` (`Medium`) with `root_cause_category = INTENTIONAL_TRADEOFF` (must NOT misclassify as accidental bug). |
| **TC-05** | Unjustified Scope Creep | PRD asks for a single-region FAQ bot; TDD introduces multi-region Kafka, custom fine-tuning, and Kubernetes without any backing business goal. | Flags `Scope Creep` (`High`) with `root_cause_category = UNJUSTIFIED_SCOPE_CREEP`. |
| **TC-06** | Ambiguous PRD + PII & Missing Section | PRD states "app should feel fast" and embeds fake email/SSN (`alice@example.com`, `123-45-6789`); TDD misses Monitoring section. | Flags `AMBIGUOUS_PRD_SPEC` on vague latency, flags missing Monitoring, redacts all PII from logs/output (`0` leaks), and handles missing file gracefully. |
| **TC-07** | Missing PRD Rule Built From Verbal Sync | PRD omits refund approval thresholds and retry policy entirely; TDD specifies *"Per 11/10 sync with Finance Ops, refunds over \$500 route to manual queue with 3 exponential retries"* with no PRD update. | Flags `PRD Backfill Required` (`Medium`) with `root_cause_category = STALE_OR_MISSING_PRD_SPEC` and `action_owner = PM / T/PgM` (must NOT misclassify as `UNJUSTIFIED_SCOPE_CREEP`). |

3. **Layer 3 — Trajectory, Routing & HITL Integration Tests:**
   - Confirms `ParallelAgent` triggers both extractors before `AlignmentAnalyzer` executes.
   - Confirms `record_alignment_decision` pauses at the HITL confirmation hook and writes zero records if the human declines.
   - Confirms Session 2 (`tdd_v2.md` or `prd_v2.md`) recalls Session 1 open Blockers and PRD backfill items via Memory Bank and marks resolved items as closed.
4. **Layer 4 — Quantitative Release Gates (Definition of Done):**
   - **Blocker Defect Recall:** `>= 90%` across TC-02, TC-03, and TC-06.
   - **False-Positive Blocker Rate:** `<= 10%` on TC-01, TC-04, and TC-07.
   - **Root-Cause ("Why") Classification Accuracy:** `>= 80%` across all 6 root-cause categories in TC-02 through TC-07.
   - **Citation Grounding Accuracy:** `>= 95%` of quoted PRD/TDD snippets match source text verbatim.
   - **PII Redaction & Security:** `0` unredacted PII tokens in logs, model payloads, or Memory Bank entries.

---

## 6. HYPOTHESES TO TEST

| Hypothesis | Core Belief | Pivot / Mitigation Plan |
| :--- | :--- | :--- |
| **Hypothesis 1: Root-Cause Distinction** | `gemini-2.5-pro` can distinguish `INTENTIONAL_TRADEOFF`, `STALE_OR_MISSING_PRD_SPEC`, and `UNJUSTIFIED_SCOPE_CREEP` from `ACCIDENTAL_OMISSION` or `UNDOCUMENTED_CONTRADICTION` at `>= 80%` accuracy when given structured section extracts. | If TC-04 or TC-07 accuracy lands below 80% in Slice 2 evals, add dedicated `documented_tradeoffs` and `unstated_business_rules_and_sync_notes` fields to `TDDArchitectureExtractor` and include 2 few-shot examples in `AlignmentAnalyzer`'s system instruction. |
| **Hypothesis 2: Section-Chunked Context Control** | Normalizing pasted text and `.docx`/`.md` uploads into heading-indexed sections (`ingest_document`, `list_doc_sections`, `read_doc_section`) prevents context bloat and achieves `>= 95%` citation grounding compared to stuffing full raw files into one prompt. | If section-level lookup misses cross-section constraints (e.g., an NFR buried in an Appendix), return a full Table-of-Contents summary on Step 1 so the extractor explicitly inspects every appendix and security heading. |
| **Hypothesis 3: Vertical-Slice Build Velocity** | Scoping Phase 1 to chat paste + `.docx`/`.md`/`.txt` uploads inside ADK Playground (deferring live Google Drive OAuth to Phase 2) allows a returning developer to build, evaluate, and deploy a 95-point rubric-ready capstone across 3 vertical slices within ~10 focused days (`0.50 PM`). | If Firestore + Agent Memory Bank integration hits environment friction in Slice 3, fall back to local SQLite `DatabaseSessionService` for revision state first, then layer Agent Runtime deployment once local `adk eval` passes 100%. |

---

## 7. SCOPE EXCLUSIONS

To protect the Phase 1 MVP timeline for a single returning developer and enforce strict 1-in-1-out scope discipline, the following boundaries are excluded from Phase 1:

| Category | Excluded Scope & Boundaries |
| :--- | :--- |
| **Logistics / Operations** | Direct Google Doc URL fetching (via 3-legged OAuth or Workspace MCP), Confluence/Notion connectors, GitHub PR webhooks, and custom React/Streamlit web frontends are excluded from Phase 1. Users paste Google Doc text (*Edit → Copy as Markdown* / copy-paste) or upload `.docx`/`.md`/`.txt` exports directly in `agents-cli playground` (`adk web`) or Agent Runtime Playground; local `.md` files are reserved for automated golden eval fixtures. |
| **Security / Identity** | Live enterprise OAuth 2.0 Drive/Jira delegation (deferred pending IT admin-allowlisted Workspace OAuth apps), enterprise SSO RBAC policies, and ingesting confidential customer or proprietary internal documents are excluded from Phase 1 (clean-room synthetic documents only). |
| **Finance / Approvals** | Automated financial/budget approvals, automated engineering gate blocking in CI/CD, and autonomous sign-off without explicit human HITL confirmation are strictly excluded. SpecAlign advises and records human-approved decisions only. |
| **Localization** | Non-English PRDs, Business Charters, and TDDs, as well as scanned image PDFs/OCR ingestion, are excluded from Phase 1 (UTF-8 English pasted text, `.docx`, `.md`, and `.txt` only). |

---

## 8. STAKEHOLDERS & BUSINESS VALUE METRICS

| Stakeholder / Metric Area | Target Details |
| :--- | :--- |
| **Project Leadership** | **Product & Engineering Owner:** SpecAlign Author \| **Capstone Reviewer:** Automated 95-Point AgentOps Evaluator |
| **User Impact** | Target enterprise user base of **30 delivery squads (~120 PRD-to-TDD design reviews per quarter)** covering TDLs, AI Activation Leads / T/PgMs, PMs, and Engineering Tech Leads. |
| **Core Value Metric** | Achieve **`>= 90%` recall on Blocker alignment defects** and **`>= 80%` root-cause classification accuracy** (including catching stale/missing PRD specs built from verbal syncs) before engineering sprint lock. |
| **Efficiency Gain** | Cut manual pre-review document cross-checking by **60%** (saving ~2.5 hours per review × 120 quarterly reviews = **1,200 hours/year**, equivalent to ~\$180K/year at \$150/hr blended engineering rate) plus avoided mid-sprint rework. |
| **Phase 1 Success** | Judged by passing all 4 evaluation gates on the 7-case planted-defect golden set (`>= 90%` Blocker recall, `<= 10%` false-positive rate, `>= 95%` citation grounding, `0` PII leaks), demonstrating stateful v1-to-v2 delta tracking + HITL sign-off, and covering all 19 criteria across the 5 pillars of the L200 95-Point AgentOps Rubric. |
| **Phase 2 Success** | Judged by autonomous PR/Doc webhook coverage across `>= 80%` of design reviews with zero manual file exports and verified Jira/GitHub Issues gap-ticket synchronization. |
