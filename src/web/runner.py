"""Synchronous pipeline runner - executes in a ThreadPoolExecutor worker thread.

Never called on the FastAPI async event loop directly; the event loop is only
touched via ``loop.call_soon_threadsafe`` inside ``JobManager._emit``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import src.main as main_module
from src.pipeline.llm import model_context
from src.web import events
from src.web.job import Job
from src.web.schemas import JobStatus, ProgressEvent

if TYPE_CHECKING:
    from src.web.job_manager import JobManager


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

    out_dir = f"{manager.settings.out_root}/{job.job_id}"
    os.makedirs(out_dir, exist_ok=True)

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

    def _stream():
        return main_module.stream_pipeline(
            resume_tex_raw=job.resume_tex_raw,
            jd_raw=job.jd_raw,
            out_dir=out_dir,
            jd_name=job.jd_name,
            enable_scoring=job.enable_scoring,
            on_step=on_step,
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
        _emit_terminal(job, manager, stage="failed")
        return

    # --- success path ---
    job.best_latex = final_state.get("best_latex")

    if job.best_latex:
        try:
            Path(out_dir, "best.tex").write_text(job.best_latex, encoding="utf-8")
        except OSError:
            pass

    job.output_pdf = final_state.get("output_pdf")
    job.output_skills = final_state.get("output_skills")
    job.score_report_md = final_state.get("score_report_md")
    job.aggregate_score = final_state.get("aggregate_score")
    job.passed = final_state.get("passed")

    job.status = JobStatus.DONE
    job.finished_at = _now()
    _emit_terminal(job, manager, stage="done")


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
