"""Persistent storage backends (Cloud Firestore Native and local SQLite) for SpecAlign.

Uses `firestore.Client(project=...)` when running on Agent Runtime (or when
`SPECALIGN_STORAGE_MODE=firestore`) and defaults to local SQLite for fast
offline development and deterministic unit tests.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


class AuditStore(Protocol):
    """Storage interface implemented by both SQLite and Firestore backends."""

    def save_audit(
        self,
        project_key: str,
        revision_label: str,
        decision_status: str,
        report: dict[str, Any],
        reviewer_note: str,
        risk_waiver_applied: bool,
    ) -> str: ...

    def get_latest_audit(self, project_key: str) -> dict[str, Any] | None: ...

    def create_gap_ticket(
        self,
        project_key: str,
        revision_label: str,
        finding: dict[str, Any],
    ) -> dict[str, Any]: ...

    def list_gap_tickets(self, project_key: str) -> list[dict[str, Any]]: ...


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteAuditStore:
    """Zero-dependency local SQLite store for offline dev and automated tests."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        with closing(sqlite3.connect(str(self.db_path), timeout=5.0)) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                yield conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audits (
                    audit_id TEXT PRIMARY KEY,
                    project_key TEXT NOT NULL,
                    revision_label TEXT NOT NULL,
                    decision_status TEXT NOT NULL,
                    overall_alignment_score INTEGER NOT NULL,
                    blocker_count INTEGER NOT NULL,
                    prd_backfill_count INTEGER NOT NULL,
                    tdd_fix_count INTEGER NOT NULL,
                    risk_waiver_applied INTEGER NOT NULL,
                    reviewer_note TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gap_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    project_key TEXT NOT NULL,
                    revision_label TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    root_cause_category TEXT NOT NULL,
                    action_owner TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save_audit(
        self,
        project_key: str,
        revision_label: str,
        decision_status: str,
        report: dict[str, Any],
        reviewer_note: str,
        risk_waiver_applied: bool,
    ) -> str:
        audit_id = f"AUDIT-{uuid.uuid4().hex[:8].upper()}"
        created_at = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audits (
                    audit_id, project_key, revision_label, decision_status,
                    overall_alignment_score, blocker_count, prd_backfill_count,
                    tdd_fix_count, risk_waiver_applied, reviewer_note,
                    report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    project_key,
                    revision_label,
                    decision_status,
                    int(report.get("overall_alignment_score", 0)),
                    int(report.get("blocker_count", 0)),
                    int(report.get("prd_backfill_count", 0)),
                    int(report.get("tdd_fix_count", 0)),
                    1 if risk_waiver_applied else 0,
                    reviewer_note,
                    json.dumps(report),
                    created_at,
                ),
            )
        return audit_id

    def get_latest_audit(self, project_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM audits
                WHERE project_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_key,),
            ).fetchone()
        if row is None:
            return None
        parsed_report = json.loads(row["report_json"])
        return {
            "audit_id": row["audit_id"],
            "project_key": row["project_key"],
            "revision_label": row["revision_label"],
            "decision_status": row["decision_status"],
            "overall_alignment_score": row["overall_alignment_score"],
            "blocker_count": row["blocker_count"],
            "prd_backfill_count": row["prd_backfill_count"],
            "tdd_fix_count": row["tdd_fix_count"],
            "risk_waiver_applied": bool(row["risk_waiver_applied"]),
            "reviewer_note": row["reviewer_note"],
            "findings": parsed_report.get("findings", []),
            "created_at": row["created_at"],
        }

    def create_gap_ticket(
        self,
        project_key: str,
        revision_label: str,
        finding: dict[str, Any],
    ) -> dict[str, Any]:
        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        created_at = _utc_now_iso()
        record = {
            "ticket_id": ticket_id,
            "project_key": project_key,
            "revision_label": revision_label,
            "finding_id": str(finding.get("finding_id", "GAP-UNKNOWN")),
            "title": str(finding.get("title", "Alignment gap")),
            "severity": str(finding.get("severity", "Medium")),
            "root_cause_category": str(
                finding.get("root_cause_category", "ACCIDENTAL_OMISSION")
            ),
            "action_owner": str(finding.get("action_owner", "Shared")),
            "recommended_action": str(finding.get("recommended_action", "Review gap.")),
            "status": "Open",
            "created_at": created_at,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gap_tickets (
                    ticket_id, project_key, revision_label, finding_id, title,
                    severity, root_cause_category, action_owner,
                    recommended_action, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["ticket_id"],
                    record["project_key"],
                    record["revision_label"],
                    record["finding_id"],
                    record["title"],
                    record["severity"],
                    record["root_cause_category"],
                    record["action_owner"],
                    record["recommended_action"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record

    def list_gap_tickets(self, project_key: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM gap_tickets
                WHERE project_key = ?
                ORDER BY created_at DESC
                """,
                (project_key,),
            ).fetchall()
        return [dict(r) for r in rows]


class FirestoreAuditStore:
    """Cloud Firestore Native store bound lazily to GOOGLE_CLOUD_PROJECT."""

    def __init__(self, project_id: str | None = None) -> None:
        self._project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._client: Any = None

    def _get_db(self) -> Any:
        if self._client is None:
            from google.cloud import firestore  # type: ignore[import-not-found]

            # Use valid google-cloud-firestore keyword `project=` (never `project_id=`).
            self._client = firestore.Client(project=self._project_id)
        return self._client

    def save_audit(
        self,
        project_key: str,
        revision_label: str,
        decision_status: str,
        report: dict[str, Any],
        reviewer_note: str,
        risk_waiver_applied: bool,
    ) -> str:
        audit_id = f"AUDIT-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "audit_id": audit_id,
            "project_key": project_key,
            "revision_label": revision_label,
            "decision_status": decision_status,
            "overall_alignment_score": int(report.get("overall_alignment_score", 0)),
            "blocker_count": int(report.get("blocker_count", 0)),
            "prd_backfill_count": int(report.get("prd_backfill_count", 0)),
            "tdd_fix_count": int(report.get("tdd_fix_count", 0)),
            "risk_waiver_applied": bool(risk_waiver_applied),
            "reviewer_note": reviewer_note,
            "findings": report.get("findings", []),
            "created_at": _utc_now_iso(),
        }
        (
            self._get_db()
            .collection("audits")
            .document(project_key)
            .collection("revisions")
            .document(audit_id)
            .set(payload)
        )
        return audit_id

    def get_latest_audit(self, project_key: str) -> dict[str, Any] | None:
        from google.cloud import firestore  # type: ignore[import-not-found]

        docs = (
            self._get_db()
            .collection("audits")
            .document(project_key)
            .collection("revisions")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
        return None

    def create_gap_ticket(
        self,
        project_key: str,
        revision_label: str,
        finding: dict[str, Any],
    ) -> dict[str, Any]:
        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "ticket_id": ticket_id,
            "project_key": project_key,
            "revision_label": revision_label,
            "finding_id": str(finding.get("finding_id", "GAP-UNKNOWN")),
            "title": str(finding.get("title", "Alignment gap")),
            "severity": str(finding.get("severity", "Medium")),
            "root_cause_category": str(
                finding.get("root_cause_category", "ACCIDENTAL_OMISSION")
            ),
            "action_owner": str(finding.get("action_owner", "Shared")),
            "recommended_action": str(finding.get("recommended_action", "Review gap.")),
            "status": "Open",
            "created_at": _utc_now_iso(),
        }
        self._get_db().collection("gap_tickets").document(ticket_id).set(record)
        return record

    def list_gap_tickets(self, project_key: str) -> list[dict[str, Any]]:
        docs = (
            self._get_db()
            .collection("gap_tickets")
            .where("project_key", "==", project_key)
            .stream()
        )
        return [doc.to_dict() for doc in docs]


def get_audit_store() -> AuditStore:
    """Resolve the active AuditStore backend based on runtime environment variables."""
    mode = os.environ.get("SPECALIGN_STORAGE_MODE", "").strip().lower()
    if not mode:
        mode = (
            "firestore" if os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID") else "sqlite"
        )
    if mode == "firestore":
        return FirestoreAuditStore()
    sqlite_path = os.environ.get("SPECALIGN_SQLITE_PATH", "data/local_audits.db")
    return SQLiteAuditStore(sqlite_path)
