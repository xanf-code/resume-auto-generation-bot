"""ResumeRepository — PostgREST wrapper for the resume_jobs table.

Accepts a Supabase client via constructor so tests can inject a mock without
touching the module-level singleton.  All methods are synchronous and safe to
call from a ThreadPoolExecutor worker.

``InMemoryResumeRepository`` implements the same CRUD surface backed by a
dict — used when Supabase is not configured (tests / offline) so JobManager
always has a single repository as source of truth.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from src.db.config import DbSettings
from src.db.models import JobRecord, record_to_row, row_to_record

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


class ResumeRepository:
    """CRUD interface for the ``resume_jobs`` Postgres table via Supabase."""

    TABLE = "resume_jobs"

    def __init__(self, client: Any, settings: DbSettings) -> None:
        self._client = client
        self._settings = settings

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, record: JobRecord) -> None:
        """Insert a new job row.  Raises on duplicate job_id."""
        row = record_to_row(record)
        self._client.table(self.TABLE).insert(row).execute()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> JobRecord | None:
        """Return the ``JobRecord`` for *job_id*, or ``None`` if not found."""
        resp = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )
        if not resp.data:
            return None
        return row_to_record(resp.data[0])

    def list(self) -> list[JobRecord]:
        """Return all jobs, ordered by ``created_at`` descending."""
        resp = (
            self._client.table(self.TABLE)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return [row_to_record(row) for row in (resp.data or [])]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def set_status(
        self,
        job_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status (and optional timestamps) of a job."""
        data: dict = {"status": status}
        if started_at is not None:
            data["started_at"] = started_at.isoformat()
        if finished_at is not None:
            data["finished_at"] = finished_at.isoformat()
        if error is not None:
            data["error"] = error
        self._client.table(self.TABLE).update(data).eq("job_id", job_id).execute()

    def save_artifacts(
        self,
        job_id: str,
        *,
        best_latex: str | None,
        output_skills: dict | None,
        score_report: dict | None,
        aggregate_score: float | None,
        passed: bool | None,
        pdf_object_key: str | None,
    ) -> None:
        """Persist pipeline artifacts for a completed job."""
        data: dict = {
            "best_latex": best_latex,
            "output_skills": output_skills,
            "score_report": score_report,
            "aggregate_score": aggregate_score,
            "passed": passed,
            "pdf_object_key": pdf_object_key,
        }
        self._client.table(self.TABLE).update(data).eq("job_id", job_id).execute()

    def rename(self, job_id: str, label: str) -> JobRecord | None:
        """Update the display label.  Returns the updated record, or ``None``."""
        resp = (
            self._client.table(self.TABLE)
            .update({"label": label})
            .eq("job_id", job_id)
            .execute()
        )
        if not resp.data:
            return None
        return row_to_record(resp.data[0])

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, job_id: str) -> bool:
        """Remove a job row.  Returns ``True`` if a row was deleted."""
        resp = (
            self._client.table(self.TABLE)
            .delete()
            .eq("job_id", job_id)
            .execute()
        )
        return bool(resp.data)

    # ------------------------------------------------------------------
    # Startup recovery
    # ------------------------------------------------------------------

    def mark_interrupted_running(self) -> int:
        """Mark any rows with status ``queued`` or ``running`` as ``failed``.

        Called at app startup to rehydrate interrupted runs that never reached
        a terminal state.  Returns the number of rows affected.
        """
        data: dict = {
            "status": "failed",
            "error": "Server restarted — run did not complete.",
            "finished_at": _now_iso(),
        }
        resp = (
            self._client.table(self.TABLE)
            .update(data)
            .in_("status", ["queued", "running"])
            .execute()
        )
        return len(resp.data or [])


class InMemoryResumeRepository:
    """Dict-backed stand-in for ``ResumeRepository`` with the same CRUD API.

    Used when Supabase credentials are absent so the web layer always reads and
    writes through a repository — never a parallel in-process job registry.
    """

    def __init__(self) -> None:
        self._rows: dict[str, JobRecord] = {}

    def create(self, record: JobRecord) -> None:
        if record.job_id in self._rows:
            raise ValueError(f"Duplicate job_id: {record.job_id}")
        self._rows[record.job_id] = record

    def get(self, job_id: str) -> JobRecord | None:
        return self._rows.get(job_id)

    def list(self) -> list[JobRecord]:
        return sorted(
            self._rows.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )

    def set_status(
        self,
        job_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        rec = self._rows.get(job_id)
        if rec is None:
            return
        updates: dict[str, Any] = {"status": status}
        if started_at is not None:
            updates["started_at"] = started_at
        if finished_at is not None:
            updates["finished_at"] = finished_at
        if error is not None:
            updates["error"] = error
        self._rows[job_id] = replace(rec, **updates)

    def save_artifacts(
        self,
        job_id: str,
        *,
        best_latex: str | None,
        output_skills: dict | None,
        score_report: dict | None,
        aggregate_score: float | None,
        passed: bool | None,
        pdf_object_key: str | None,
    ) -> None:
        rec = self._rows.get(job_id)
        if rec is None:
            return
        self._rows[job_id] = replace(
            rec,
            best_latex=best_latex,
            output_skills=output_skills,
            score_report=score_report,
            aggregate_score=aggregate_score,
            passed=passed,
            pdf_object_key=pdf_object_key,
        )

    def rename(self, job_id: str, label: str) -> JobRecord | None:
        rec = self._rows.get(job_id)
        if rec is None:
            return None
        updated = replace(rec, label=label)
        self._rows[job_id] = updated
        return updated

    def delete(self, job_id: str) -> bool:
        return self._rows.pop(job_id, None) is not None

    def mark_interrupted_running(self) -> int:
        n = 0
        finished = _now()
        for job_id, rec in list(self._rows.items()):
            if rec.status in ("queued", "running"):
                self._rows[job_id] = replace(
                    rec,
                    status="failed",
                    error="Server restarted — run did not complete.",
                    finished_at=finished,
                )
                n += 1
        return n
