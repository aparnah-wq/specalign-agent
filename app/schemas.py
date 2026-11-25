"""Pydantic v2 domain models, citation grounding verifier, and scorecard renderer.

Enforces strict JSON contracts across SpecAlign's 4-agent pipeline, including
bi-directional alignment status, severity, action-owner routing, and the
6-category drift root-cause taxonomy.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel, Field
    from pydantic import ValidationError as SchemaValidationError
else:
    try:
        from pydantic import BaseModel, Field
        from pydantic import ValidationError as SchemaValidationError
    except ImportError:
        from app._compat_pydantic import BaseModel, Field, SchemaValidationError


class AlignmentStatus(str, Enum):
    """Bi-directional coverage state between PRD/Business Goals and TDD."""

    ALIGNED = "ALIGNED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    MISSING = "MISSING"
    CONTRADICTION = "CONTRADICTION"
    SCOPE_CREEP = "SCOPE_CREEP"
    PRD_BACKFILL_REQUIRED = "PRD_BACKFILL_REQUIRED"


class Severity(str, Enum):
    """Risk severity governing sign-off and escalation gates."""

    BLOCKER = "Blocker"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class RootCauseCategory(str, Enum):
    """Six-category drift root-cause taxonomy explaining why TDD diverged from PRD."""

    ALIGNED = "ALIGNED"
    INTENTIONAL_TRADEOFF = "INTENTIONAL_TRADEOFF"
    ACCIDENTAL_OMISSION = "ACCIDENTAL_OMISSION"
    UNDOCUMENTED_CONTRADICTION = "UNDOCUMENTED_CONTRADICTION"
    UNJUSTIFIED_SCOPE_CREEP = "UNJUSTIFIED_SCOPE_CREEP"
    AMBIGUOUS_PRD_SPEC = "AMBIGUOUS_PRD_SPEC"
    STALE_OR_MISSING_PRD_SPEC = "STALE_OR_MISSING_PRD_SPEC"


class ActionOwner(str, Enum):
    """Role accountable for closing a finding before or after design sign-off."""

    ENGINEERING = "Engineering"
    PM = "PM"
    PM_TPGM = "PM / T/PgM"
    SHARED = "Shared"


class RequirementItem(BaseModel):
    """Single business goal, functional requirement, NFR, or scope exclusion from PRD/Charter."""

    requirement_id: str = Field(
        ..., min_length=2, description="Stable ID such as REQ-001 or KPI-001"
    )
    category: str = Field(
        ..., description="Business Goal, Functional, NFR, Compliance, or Out-of-Scope"
    )
    priority: str = Field(
        ..., description="Must-Have, Nice-to-Have, or Scope Exclusion"
    )
    summary: str = Field(..., min_length=5)
    is_vague: bool = Field(
        default=False,
        description="True when requirement lacks measurable criteria (e.g. 'fast' or 'scalable')",
    )
    source_section: str = Field(
        ..., description="Exact heading where this item appears"
    )
    verbatim_quote: str = Field(
        ..., min_length=3, description="Exact quote from PRD or Charter"
    )


class PRDExtract(BaseModel):
    """Structured output emitted by PRDGoalExtractor."""

    requirements: list[RequirementItem] = Field(default_factory=list)
    business_kpis: list[str] = Field(default_factory=list)
    scope_exclusions: list[str] = Field(default_factory=list)


class TDDComponentItem(BaseModel):
    """Single architecture component, data store, SLA, or security control from TDD."""

    component_name: str = Field(..., min_length=2)
    purpose: str = Field(..., min_length=5)
    region_or_constraint: str = Field(default="Unspecified")
    source_section: str
    verbatim_quote: str = Field(..., min_length=3)


class DocumentedTradeoff(BaseModel):
    """Explicit engineering trade-off where the TDD justifies deviating from a PRD target."""

    topic: str = Field(..., min_length=3)
    decision: str = Field(..., min_length=5)
    constraint_rationale: str = Field(..., min_length=5)
    source_section: str
    verbatim_quote: str = Field(..., min_length=3)


class UnstatedBusinessRule(BaseModel):
    """Concrete rule or workflow built in TDD from verbal syncs/meetings with no PRD anchor."""

    rule_summary: str = Field(..., min_length=5)
    verbal_decision_cue: str = Field(
        default="None cited",
        description="Phrase such as 'per Tuesday sync' or 'agreed with Finance Ops'",
    )
    source_section: str
    verbatim_quote: str = Field(..., min_length=3)


class TDDExtract(BaseModel):
    """Structured output emitted by TDDArchitectureExtractor."""

    components: list[TDDComponentItem] = Field(default_factory=list)
    documented_tradeoffs: list[DocumentedTradeoff] = Field(default_factory=list)
    unstated_business_rules_and_sync_notes: list[UnstatedBusinessRule] = Field(
        default_factory=list
    )


class AlignmentFinding(BaseModel):
    """Single evidence-grounded alignment item comparing PRD/Business Goals against TDD."""

    finding_id: str = Field(..., min_length=3, description="Stable ID such as GAP-001")
    requirement_ref: str = Field(
        ..., min_length=2, description="PRD/OKR ID or 'TDD-ONLY'"
    )
    title: str = Field(..., min_length=5, max_length=140)
    alignment_status: AlignmentStatus
    severity: Severity
    root_cause_category: RootCauseCategory
    action_owner: ActionOwner
    prd_section: str = Field(..., description="Exact PRD/Charter heading or 'None'")
    prd_quote: str = Field(
        ..., description="Verbatim excerpt from PRD or 'Not present in PRD'"
    )
    tdd_section: str = Field(..., description="Exact TDD heading or 'None'")
    tdd_quote: str = Field(
        ..., description="Verbatim excerpt from TDD or 'Not present in TDD'"
    )
    rationale: str = Field(
        ..., min_length=5, description="Concise explanation of why drift occurred"
    )
    recommended_action: str = Field(
        ..., min_length=5, description="Concrete TDD fix or PRD backfill"
    )


class AlignmentReport(BaseModel):
    """Top-level structured report produced by AlignmentAnalyzer."""

    project_key: str = Field(..., min_length=2)
    revision_label: str = Field(..., min_length=1)
    overall_alignment_score: int = Field(..., ge=0, le=100)
    blocker_count: int = Field(..., ge=0)
    prd_backfill_count: int = Field(..., ge=0)
    tdd_fix_count: int = Field(..., ge=0)
    findings: list[AlignmentFinding] = Field(default_factory=list)
    delta_from_previous: list[str] = Field(
        default_factory=list,
        description="Summary of blockers closed, still open, or newly introduced vs prior audit",
    )


_SENTINEL_QUOTES: frozenset[str] = frozenset(
    {"not present in prd", "not present in tdd", "none", "n/a", ""}
)
_PRD_BACKFILL_CAUSES: frozenset[str] = frozenset(
    {
        RootCauseCategory.STALE_OR_MISSING_PRD_SPEC.value,
        RootCauseCategory.AMBIGUOUS_PRD_SPEC.value,
        RootCauseCategory.INTENTIONAL_TRADEOFF.value,
    }
)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _normalize_quote(text: str) -> str:
    return _normalize_ws(text).strip("\"'`.,;: ")


def verify_report_citations(
    report_dict: dict[str, Any],
    ingested_docs: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Deterministically verify that quoted PRD/TDD snippets appear verbatim in ingested docs.

    Args:
        report_dict: Serialized `AlignmentReport` dictionary.
        ingested_docs: `session.state["ingested_docs"]` mapping role -> `{heading: body}`.

    Returns:
        Dictionary containing `total_quotes_checked`, `grounded_quotes`,
        `grounding_rate` (0.0–1.0), and `ungrounded_findings`.
    """
    prd_corpus = _normalize_ws(
        " ".join(
            list(ingested_docs.get("prd", {}).values())
            + list(ingested_docs.get("business_goals", {}).values())
        )
    )
    tdd_corpus = _normalize_ws(" ".join(ingested_docs.get("tdd", {}).values()))

    total_checked = 0
    grounded_count = 0
    ungrounded: list[dict[str, str]] = []

    for finding in report_dict.get("findings", []):
        fid = str(finding.get("finding_id", "UNKNOWN"))
        for side, quote_key, corpus in (
            ("prd", "prd_quote", prd_corpus),
            ("tdd", "tdd_quote", tdd_corpus),
        ):
            raw_quote = str(finding.get(quote_key, "")).strip()
            norm_quote = _normalize_quote(raw_quote)
            if norm_quote in _SENTINEL_QUOTES:
                continue
            total_checked += 1
            if norm_quote and norm_quote in corpus:
                grounded_count += 1
            else:
                ungrounded.append(
                    {
                        "finding_id": fid,
                        "side": side,
                        "unmatched_quote": raw_quote[:160],
                    }
                )

    grounding_rate = (
        1.0 if total_checked == 0 else round(grounded_count / total_checked, 4)
    )
    return {
        "status": "pass" if grounding_rate >= 0.95 else "needs_review",
        "total_quotes_checked": total_checked,
        "grounded_quotes": grounded_count,
        "grounding_rate": grounding_rate,
        "ungrounded_findings": ungrounded,
    }


def render_executive_scorecard(report_dict: dict[str, Any]) -> str:
    """Render an AlignmentReport dict into a scannable Markdown Executive Scorecard.

    Splits actionable items into two explicit queues:
    1. Engineering TDD Fixes (omissions, contradictions, scope creep)
    2. PM & T/PgM PRD Backfills (stale/missing PRD specs, vague specs, documented trade-offs)
    """
    project = report_dict.get("project_key", "unknown")
    rev = report_dict.get("revision_label", "v1")
    score = report_dict.get("overall_alignment_score", 0)
    blockers = report_dict.get("blocker_count", 0)
    tdd_fixes_count = report_dict.get("tdd_fix_count", 0)
    prd_backfills_count = report_dict.get("prd_backfill_count", 0)

    tdd_fixes: list[dict[str, Any]] = []
    prd_backfills: list[dict[str, Any]] = []
    for f in report_dict.get("findings", []):
        status = str(f.get("alignment_status", ""))
        cause = str(f.get("root_cause_category", ""))
        owner = str(f.get("action_owner", ""))
        if status == AlignmentStatus.ALIGNED.value:
            continue
        if (
            status == AlignmentStatus.PRD_BACKFILL_REQUIRED.value
            or cause in _PRD_BACKFILL_CAUSES
            or owner in (ActionOwner.PM.value, ActionOwner.PM_TPGM.value)
        ):
            prd_backfills.append(f)
        else:
            tdd_fixes.append(f)

    lines = [
        f"# SpecAlign Executive Scorecard — `{project}` ({rev})",
        "",
        f"- **Alignment Score:** `{score}/100`",
        f"- **Open Blockers:** `{blockers}`",
        f"- **Engineering TDD Fixes:** `{tdd_fixes_count}` | **PM & T/PgM PRD Backfills:** `{prd_backfills_count}`",
        "",
        "## Engineering TDD Fixes",
    ]
    if not tdd_fixes:
        lines.append("- None.")
    else:
        for item in tdd_fixes:
            lines.append(
                f"- **{item['finding_id']} [{item['severity']}] ({item['root_cause_category']})** — "
                f"{item['title']} *(Owner: {item['action_owner']})*: {item['recommended_action']}"
            )

    lines.extend(["", "## PM & T/PgM PRD Backfills"])
    if not prd_backfills:
        lines.append("- None.")
    else:
        for item in prd_backfills:
            lines.append(
                f"- **{item['finding_id']} [{item['severity']}] ({item['root_cause_category']})** — "
                f"{item['title']} *(Owner: {item['action_owner']})*: {item['recommended_action']}"
            )

    deltas = report_dict.get("delta_from_previous", [])
    if deltas:
        lines.extend(["", "## Revision Delta vs. Prior Audit"])
        for entry in deltas:
            lines.append(f"- {entry}")

    return "\n".join(lines)


__all__ = [
    "ActionOwner",
    "AlignmentFinding",
    "AlignmentReport",
    "AlignmentStatus",
    "DocumentedTradeoff",
    "PRDExtract",
    "RequirementItem",
    "RootCauseCategory",
    "SchemaValidationError",
    "Severity",
    "TDDComponentItem",
    "TDDExtract",
    "UnstatedBusinessRule",
    "render_executive_scorecard",
    "verify_report_citations",
]
