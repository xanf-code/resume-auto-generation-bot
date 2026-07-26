"""Synchronous pipeline runner - executes in a ThreadPoolExecutor worker thread.

Never called on the FastAPI async event loop directly; the event loop is only
touched via ``loop.call_soon_threadsafe`` inside ``JobManager._emit``.

The worker mutates the ephemeral runtime ``Job`` for SSE progress. Durable
status and artifacts are written through ``manager._repo`` (the source of
truth for subsequent HTTP reads). Persistence failures are logged; API
responses always re-read from the repository.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import src.main as main_module
from src.pipeline.emit import build_score_report
from src.pipeline.llm import model_context
from src.web import events
from src.web.job import Job
from src.web.schemas import JobStatus, ProgressEvent

if TYPE_CHECKING:
    from src.web.job_manager import JobManager

log = logging.getLogger(__name__)


class JobCancelled(Exception):
    """Raised from within ``on_step`` to abort a running pipeline.

    The stream loop calls ``on_step`` after every node; raising here unwinds
    ``graph.stream`` cleanly at the next node boundary so an aborted job stops
    without leaving a worker thread spinning.
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_job(job: Job, manager: "JobManager") -> None:
    """Execute the pipeline for *job* synchronously (called from a worker thread)."""
    job.status = JobStatus.RUNNING
    job.started_at = _now()
    _db_set_status(job, manager, status="running", started_at=job.started_at)

    # Web path writes nothing to the local out/ tree — Supabase is the only
    # sink. emit() ignores out_dir when write_files=False, so we neither compute
    # nor create a local directory here; the compiled PDF is uploaded straight
    # from the compiler's temp path.
    out_dir = ""

    def on_step(flat_delta: dict, state: dict) -> None:
        if job.cancel_event.is_set():
            raise JobCancelled()
        event = events.build_progress_event(job.job_id, flat_delta, state)
        if event is not None:
            manager._emit(job, event)

    # Forward the per-application tuning only when set - a None config keeps the
    # call shape (and the pipeline's default behaviour) exactly as before.
    extra: dict = {}
    if job.tuning is not None:
        extra["tuning"] = job.tuning
    if job.bullet_shapes is not None:
        extra["bullet_shapes"] = job.bullet_shapes

    def _stream():
        return main_module.stream_pipeline(
            resume_tex_raw=job.resume_tex_raw,
            jd_raw=job.jd_raw,
            out_dir=out_dir,
            jd_name=job.jd_name,
            enable_scoring=job.enable_scoring,
            on_step=on_step,
            write_files=False,  # web path: score_report.json/skills.json are dead writes
            **extra,
        )

    try:
        if job.models is not None:
            with model_context(
                fast=job.models.parser.model,
                strong=job.models.writer.model,
                gap=job.models.gap.model,
                scoring=job.models.scoring.model,
                effort_fast=job.models.parser.effort,
                effort_strong=job.models.writer.effort,
                effort_gap=job.models.gap.effort,
                effort_scoring=job.models.scoring.effort,
            ):
                final_state = _stream()
        else:
            final_state = _stream()
    except JobCancelled:
        job.status = JobStatus.FAILED
        job.error = "You stopped this run before it finished."
        job.finished_at = _now()
        _db_set_status(job, manager, status="failed", finished_at=job.finished_at, error=job.error)
        _emit_terminal(job, manager, stage="failed", human_label="Stopped")
        return
    except Exception as exc:
        job.status = JobStatus.FAILED
        exc_type_name = type(exc).__name__
        if "GraphRecursionError" in exc_type_name:
            job.error = "Pipeline hit recursion limit - try fewer max iterations."
        else:
            job.error = str(exc)
        job.finished_at = _now()
        _db_set_status(job, manager, status="failed", finished_at=job.finished_at, error=job.error)
        _emit_terminal(job, manager, stage="failed")
        return

    # --- success path ---
    job.best_latex = final_state.get("best_latex")
    job.output_pdf = final_state.get("output_pdf")
    job.score_report_md = final_state.get("score_report_md")
    job.aggregate_score = final_state.get("aggregate_score")
    job.passed = final_state.get("passed")

    # Stage JSON artifacts on the runtime job, then persist via the repository.
    job.score_report = build_score_report(final_state)
    skill_dump = final_state.get("skill_dump")
    job.output_skills = skill_dump.model_dump() if skill_dump is not None else None

    job.status = JobStatus.DONE
    job.finished_at = _now()

    _db_save_artifacts(job, manager)

    _emit_terminal(job, manager, stage="done")


# ---------------------------------------------------------------------------
# Repository helpers (repo is always present — real or in-memory)
# ---------------------------------------------------------------------------

def _db_set_status(
    job: "Job",
    manager: "JobManager",
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error: str | None = None,
) -> None:
    """Persist a status transition to the repository."""
    try:
        manager._repo.set_status(
            job.job_id,
            status,
            started_at=started_at,
            finished_at=finished_at,
            error=error,
        )
    except Exception:
        log.exception("Failed to set status %s for job %s", status, job.job_id)


def _db_save_artifacts(
    job: "Job",
    manager: "JobManager",
) -> None:
    """Upload PDF to Storage (when configured) and persist artifacts to the repo.

    Each step is isolated: a storage upload failure never blocks the artifact
    save, and neither blocks the final status update to "done".  Storage is the
    durable home for the PDF; ``job.output_pdf`` points at the compiler's temp
    PDF (no local out/ copy is made), which is deleted after this function
    returns regardless of upload outcome.
    """
    from src.web.config import _optional_db_settings
    from src.db.client import get_client
    from src.db.storage import upload_pdf

    # Step 1 — upload PDF to Storage (best-effort; skipped without Supabase).
    pdf_object_key: str | None = None
    local_pdf = job.output_pdf if (job.output_pdf and os.path.isfile(job.output_pdf)) else None
    if local_pdf:
        db_settings = _optional_db_settings()
        if db_settings is not None:
            try:
                pdf_object_key = upload_pdf(
                    job.job_id, local_pdf, get_client(db_settings), db_settings.bucket
                )
                job.pdf_object_key = pdf_object_key
            except Exception:
                log.exception("Failed to upload PDF to Storage for job %s", job.job_id)
        try:
            os.remove(local_pdf)
        except OSError:
            log.warning("Failed to delete staged PDF for job %s", job.job_id)

    # Step 2 — save artifacts (best-effort).
    try:
        manager._repo.save_artifacts(
            job.job_id,
            best_latex=job.best_latex,
            output_skills=job.output_skills,
            score_report=job.score_report,
            aggregate_score=job.aggregate_score,
            passed=job.passed,
            pdf_object_key=pdf_object_key or job.pdf_object_key,
        )
    except Exception:
        log.exception("Failed to save artifacts for job %s", job.job_id)

    # Step 3 — mark done; always runs even if steps above failed.
    try:
        manager._repo.set_status(job.job_id, "done", finished_at=job.finished_at)
    except Exception:
        log.exception("Failed to set done status for job %s", job.job_id)


def _emit_terminal(
    job: Job,
    manager: "JobManager",
    stage: str,
    human_label: str | None = None,
) -> None:
    """Emit a synthetic terminal event (done or failed) to all subscribers.

    Carries ``job.error`` on failure so subscribers can render the reason
    without a separate detail fetch.
    """
    default_label = "Done" if stage == "done" else "Failed"
    detail = "Run complete - artifacts ready" if stage == "done" else job.error
    terminal = ProgressEvent(
        job_id=job.job_id,
        stage=stage,
        human_label=human_label or default_label,
        pct=100 if stage == "done" else 0,
        aggregate_score=job.aggregate_score,
        passed=job.passed,
        detail=detail,
        error=None if stage == "done" else job.error,
    )
    manager._emit(job, terminal)
