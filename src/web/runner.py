"""Synchronous pipeline runner — executes in a ThreadPoolExecutor worker thread.

Never called on the FastAPI async event loop directly; the event loop is only
touched via ``loop.call_soon_threadsafe`` inside ``JobManager._emit``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import src.main as main_module
from src.web import events
from src.web.job import Job
from src.web.schemas import JobStatus, ProgressEvent

if TYPE_CHECKING:
    from src.web.job_manager import JobManager


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_job(job: Job, manager: "JobManager") -> None:
    """Execute the pipeline for *job* synchronously (called from a worker thread)."""
    job.status = JobStatus.RUNNING
    job.started_at = _now()

    out_dir = f"{manager.settings.out_root}/{job.job_id}"
    os.makedirs(out_dir, exist_ok=True)

    def on_step(flat_delta: dict, state: dict) -> None:
        event = events.build_progress_event(job.job_id, flat_delta, state)
        if event is not None:
            manager._emit(job, event)

    try:
        final_state = main_module.stream_pipeline(
            resume_tex_raw=job.resume_tex_raw,
            jd_raw=job.jd_raw,
            out_dir=out_dir,
            jd_name=job.jd_name,
            enable_scoring=job.enable_scoring,
            on_step=on_step,
        )
    except Exception as exc:
        job.status = JobStatus.FAILED
        exc_type_name = type(exc).__name__
        if "GraphRecursionError" in exc_type_name:
            job.error = "Pipeline hit recursion limit — try fewer max iterations."
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


def _emit_terminal(job: Job, manager: "JobManager", stage: str) -> None:
    """Emit a synthetic terminal event (done or failed) to all subscribers."""
    terminal = ProgressEvent(
        job_id=job.job_id,
        stage=stage,
        human_label="Done" if stage == "done" else "Failed",
        pct=100 if stage == "done" else 0,
        aggregate_score=job.aggregate_score,
        passed=job.passed,
    )
    manager._emit(job, terminal)
