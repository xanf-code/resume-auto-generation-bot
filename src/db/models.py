"""JobRecord dataclass and row-conversion helpers for the resume_jobs table.

``JobRecord`` is a frozen (immutable) dataclass that mirrors the Postgres row.
``record_to_row`` and ``row_to_record`` handle the datetime ↔ ISO-string
conversion needed at the Supabase boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class JobRecord:
    """Immutable representation of a resume_jobs row."""

    # --- identity ---
    job_id: str
    label: str
    status: str  # "queued" | "running" | "done" | "failed"
    created_at: datetime

    # --- optional timestamps ---
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    user_id: str | None = None

    # --- inputs ---
    resume_tex_raw: str = ""
    jd_raw: str = ""
    jd_name: str = ""
    enable_scoring: bool = False
    tuning: dict | None = None
    models: dict | None = None
    bullet_shapes: list | None = None
    role_bullet_counts: list | None = None

    # --- JD classification (computed by run_job; not user input) ---
    role: str | None = None
    domains: list | None = None

    # --- artifacts ---
    best_latex: str | None = None
    output_skills: dict | None = None
    score_report: dict | None = None
    aggregate_score: float | None = None
    passed: bool | None = None
    pdf_object_key: str | None = None


def _dt_to_iso(dt: datetime | None) -> str | None:
    """Convert a datetime to an ISO-8601 string, or return None."""
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a datetime, or return None."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


def record_to_row(rec: JobRecord) -> dict:
    """Serialize a ``JobRecord`` to a plain dict suitable for Supabase upsert.

    Datetimes are converted to ISO-8601 strings; all other types are passed
    through as-is (Supabase / PostgREST handles JSON serialization).
    """
    return {
        "job_id": rec.job_id,
        "label": rec.label,
        "status": rec.status,
        "created_at": _dt_to_iso(rec.created_at),
        "started_at": _dt_to_iso(rec.started_at),
        "finished_at": _dt_to_iso(rec.finished_at),
        "error": rec.error,
        "user_id": rec.user_id,
        "resume_tex_raw": rec.resume_tex_raw,
        "jd_raw": rec.jd_raw,
        "jd_name": rec.jd_name,
        "enable_scoring": rec.enable_scoring,
        "tuning": rec.tuning,
        "models": rec.models,
        "bullet_shapes": rec.bullet_shapes,
        "role_bullet_counts": rec.role_bullet_counts,
        "role": rec.role,
        "domains": rec.domains,
        "best_latex": rec.best_latex,
        "output_skills": rec.output_skills,
        "score_report": rec.score_report,
        "aggregate_score": rec.aggregate_score,
        "passed": rec.passed,
        "pdf_object_key": rec.pdf_object_key,
    }


def row_to_record(row: dict) -> JobRecord:
    """Deserialize a Supabase row dict to a ``JobRecord``.

    ISO-8601 strings are parsed back to ``datetime`` objects.  Missing or None
    datetime fields are left as ``None``.
    """
    return JobRecord(
        job_id=row["job_id"],
        label=row["label"],
        status=row["status"],
        created_at=_iso_to_dt(row["created_at"]),  # type: ignore[arg-type]
        started_at=_iso_to_dt(row.get("started_at")),
        finished_at=_iso_to_dt(row.get("finished_at")),
        error=row.get("error"),
        user_id=row.get("user_id"),
        resume_tex_raw=row.get("resume_tex_raw", ""),
        jd_raw=row.get("jd_raw", ""),
        jd_name=row.get("jd_name", ""),
        enable_scoring=row.get("enable_scoring", False),
        tuning=row.get("tuning"),
        models=row.get("models"),
        bullet_shapes=row.get("bullet_shapes"),
        role_bullet_counts=row.get("role_bullet_counts"),
        role=row.get("role"),
        domains=row.get("domains"),
        best_latex=row.get("best_latex"),
        output_skills=row.get("output_skills"),
        score_report=row.get("score_report"),
        aggregate_score=row.get("aggregate_score"),
        passed=row.get("passed"),
        pdf_object_key=row.get("pdf_object_key"),
    )
