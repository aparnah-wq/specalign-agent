"""HITL-gated alignment decision tools, baseline lookup, and revision delta utilities."""

from __future__ import annotations

from typing import Any

from app.schemas import render_executive_scorecard, verify_report_citations
from app.storage import get_audit_store
from app.telemetry import trace_tool_call

try:
    from google.adk.tools import ToolContext
except ImportError:  # Offline unit testing without google-adk installed.
    ToolContext = Any  # type: ignore[misc, assignment]

VALID_DECISION_STATUSES: frozenset[str] = frozenset({"Approved", "Changes Requested"})


def _get_state(tool_context: ToolContext | None) -> dict[str, Any]:
    if tool_context is None:
        return {}
    state = getattr(tool_context, "state", None)
    return state if state is not None else {}


def _error(error_code: str, message: str, recovery_guidance: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "recovery_guidance": recovery_guidance,
    }


@trace_tool_call()
def get_previous_audit(
    project_key: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Retrieve the latest saved alignment audit baseline and open gap tickets for a project.

    Hydrates `session.state["previous_audit"]` so the alignment analyzer can
    compare Revision v2 against Revision v1 and report closed vs. remaining gaps.

    Args:
        project_key: Unique project slug (e.g. `'checkout-refunds'`).
        tool_context: ADK-injected context providing mutable `session.state`.

    Returns:
        Dictionary with `status='success'`, `audit`, and `open_tickets`, or
        `status='not_found'` when no prior baseline exists.
    """
    clean_key = project_key.strip()
    if not clean_key:
        return _error(
            "INVALID_PROJECT_KEY",
            "project_key must be a non-empty string.",
            "Ask the user for a short project name or slug such as 'checkout-refunds'.",
        )

    store = get_audit_store()
    state = _get_state(tool_context)
    state["project_key"] = clean_key

    latest = store.get_latest_audit(clean_key)
    if latest is None:
        state["previous_audit"] = None
        return {
            "status": "not_found",
            "project_key": clean_key,
            "message": "No prior audit baseline exists; treat this run as Revision v1.",
        }

    tickets = store.list_gap_tickets(clean_key)
    state["previous_audit"] = latest
    return {
        "status": "success",
        "project_key": clean_key,
        "audit": latest,
        "open_tickets": tickets,
    }


@trace_tool_call()
def verify_alignment_citations(
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Deterministically verify that quotes in `session.state['alignment_report']` match source docs.

    Args:
        tool_context: ADK-injected context containing `alignment_report` and `ingested_docs`.

    Returns:
        Citation grounding summary (`grounding_rate`, `ungrounded_findings`) plus
        a formatted Markdown Executive Scorecard.
    """
    state = _get_state(tool_context)
    report = state.get("alignment_report")
    ingested_docs = state.get("ingested_docs", {})
    if not isinstance(report, dict):
        return _error(
            "MISSING_ALIGNMENT_REPORT",
            "No alignment_report found in session state.",
            "Run the alignment_audit_pipeline before verifying citations.",
        )

    grounding = verify_report_citations(report, ingested_docs)
    scorecard = render_executive_scorecard(report)
    return {
        "status": "success",
        "grounding": grounding,
        "scorecard_markdown": scorecard,
    }


def compute_revision_delta(
    previous_audit: dict[str, Any],
    current_report: dict[str, Any],
) -> dict[str, Any]:
    """Compute a deterministic diff between a prior saved audit baseline and a new report.

    Args:
        previous_audit: Stored baseline dict from Revision v1.
        current_report: Newly produced `AlignmentReport` dict for Revision v2.

    Returns:
        Structured diff listing `score_change`, `closed_finding_ids`,
        `still_open_finding_ids`, `new_finding_ids`, and `delta_summary`.
    """
    prev_findings = {
        str(f.get("finding_id")): f
        for f in previous_audit.get("findings", [])
        if f.get("finding_id")
    }
    curr_findings = {
        str(f.get("finding_id")): f
        for f in current_report.get("findings", [])
        if f.get("finding_id")
    }

    prev_ids = set(prev_findings.keys())
    curr_ids = set(curr_findings.keys())

    closed_ids = sorted(prev_ids - curr_ids)
    still_open_ids = sorted(prev_ids & curr_ids)
    new_ids = sorted(curr_ids - prev_ids)

    prev_score = int(previous_audit.get("overall_alignment_score", 0))
    curr_score = int(current_report.get("overall_alignment_score", 0))
    score_change = curr_score - prev_score

    summary: list[str] = [
        f"Alignment score changed from {prev_score}/100 to {curr_score}/100 ({score_change:+d})."
    ]
    if closed_ids:
        summary.append(f"Closed prior findings: {', '.join(closed_ids)}.")
    if still_open_ids:
        summary.append(f"Still open from prior revision: {', '.join(still_open_ids)}.")
    if new_ids:
        summary.append(f"Newly introduced findings: {', '.join(new_ids)}.")

    return {
        "score_change": score_change,
        "closed_finding_ids": closed_ids,
        "still_open_finding_ids": still_open_ids,
        "new_finding_ids": new_ids,
        "delta_summary": summary,
    }


@trace_tool_call()
def record_alignment_decision(
    project_key: str,
    revision_label: str,
    decision_status: str,
    approved_ticket_ids: list[str],
    reviewer_note: str = "",
    human_confirmed: bool = False,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Persist a formal design-review decision and open gap tickets behind a mandatory HITL gate.

    Never writes to Firestore or SQLite until `human_confirmed=True` (and ADK
    tool confirmation is accepted). Approving a review while `blocker_count > 0`
    also requires a non-empty written risk-waiver note in `reviewer_note`.

    Args:
        project_key: Project slug such as `'checkout-refunds'`.
        revision_label: Revision tag such as `'v1'` or `'v2'`.
        decision_status: Must be `'Approved'` or `'Changes Requested'`.
        approved_ticket_ids: List of finding IDs (e.g. `['GAP-001']`) to log as gap tickets.
        reviewer_note: Reviewer comment or mandatory risk waiver when approving with Blockers.
        human_confirmed: Must be `True` only after explicit human approval.
        tool_context: ADK-injected context holding `alignment_report`.

    Returns:
        Either an `awaiting_human_confirmation` prompt, a guided error envelope,
        or `status='success'` with persisted `audit_id` and `created_tickets`.
    """
    if decision_status not in VALID_DECISION_STATUSES:
        return _error(
            "INVALID_DECISION_STATUS",
            f"Unsupported decision_status '{decision_status}'.",
            "Use either 'Approved' or 'Changes Requested'.",
        )

    state = _get_state(tool_context)
    report = state.get("alignment_report")
    if not isinstance(report, dict):
        return _error(
            "MISSING_ALIGNMENT_REPORT",
            "Cannot record a decision before an alignment_report exists in session state.",
            "Run the alignment audit first, review findings with the user, then retry.",
        )

    blocker_count = int(report.get("blocker_count", 0))
    prd_backfill_count = int(report.get("prd_backfill_count", 0))
    findings_by_id = {str(f.get("finding_id")): f for f in report.get("findings", [])}
    selected_findings = [
        findings_by_id.get(
            fid,
            {
                "finding_id": fid,
                "title": f"Follow-up action for {fid}",
                "severity": "Medium",
                "root_cause_category": "ACCIDENTAL_OMISSION",
                "action_owner": "Shared",
                "recommended_action": "Review alignment finding.",
            },
        )
        for fid in approved_ticket_ids
    ]

    # Defense-in-depth Layer 1: explicit human confirmation required before any write.
    if not human_confirmed:
        staged = {
            "project_key": project_key,
            "revision_label": revision_label,
            "decision_status": decision_status,
            "approved_ticket_ids": approved_ticket_ids,
            "reviewer_note": reviewer_note,
            "blocker_count": blocker_count,
            "prd_backfill_count": prd_backfill_count,
        }
        state["hitl_pending_decision"] = staged
        return {
            "status": "awaiting_human_confirmation",
            "project_key": project_key,
            "revision_label": revision_label,
            "decision_status": decision_status,
            "blocker_count": blocker_count,
            "prd_backfill_count": prd_backfill_count,
            "proposed_ticket_ids": approved_ticket_ids,
            "message": (
                f"Confirmation required before saving '{decision_status}' for '{project_key}' "
                f"({revision_label}): {blocker_count} open Blocker(s), "
                f"{prd_backfill_count} PRD backfill item(s), "
                f"{len(approved_ticket_ids)} ticket(s) queued."
            ),
            "recovery_guidance": (
                "Present this summary to the human reviewer and re-invoke with "
                "human_confirmed=True only after they explicitly confirm."
            ),
        }

    # Defense-in-depth Layer 2: approving with open Blockers requires a written waiver.
    risk_waiver_applied = False
    if decision_status == "Approved" and blocker_count > 0:
        if not reviewer_note.strip():
            return _error(
                "BLOCKER_WAIVER_REQUIRED",
                f"Cannot record 'Approved' while {blocker_count} open Blocker(s) remain without a written waiver.",
                "Ask the human reviewer to either switch decision_status to 'Changes Requested' "
                "or supply an explicit risk-waiver justification in reviewer_note.",
            )
        risk_waiver_applied = True

    store = get_audit_store()
    audit_id = store.save_audit(
        project_key=project_key,
        revision_label=revision_label,
        decision_status=decision_status,
        report=report,
        reviewer_note=reviewer_note,
        risk_waiver_applied=risk_waiver_applied,
    )
    created_tickets = [
        store.create_gap_ticket(project_key, revision_label, finding)
        for finding in selected_findings
    ]
    state["hitl_pending_decision"] = None

    return {
        "status": "success",
        "audit_id": audit_id,
        "project_key": project_key,
        "revision_label": revision_label,
        "decision_status": decision_status,
        "risk_waiver_applied": risk_waiver_applied,
        "created_tickets": created_tickets,
        "scorecard_markdown": render_executive_scorecard(report),
    }
