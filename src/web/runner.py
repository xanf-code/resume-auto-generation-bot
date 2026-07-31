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
from pathlib import Path
from typing import TYPE_CHECKING

import src.main as main_module
from src.agents.jd_tagger import JdClassification, classify_jd_type
from src.pipeline.emit import build_score_report
from src.pipeline.llm import model_context
from src.vault.config import VaultSettings
from src.vault.retrieval import retrieve_examples
from src.vault.tuning import resolve_tuning
from src.vault.writer import write_run_note
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


def _vault_retrieval_event(job: Job, classification: JdClassification, found: bool) -> ProgressEvent:
    """Build a visibility event for the proven-examples lookup (Loop A, read side)."""
    tags = classification.combined_tags
    tag_label = ", ".join(tags) if tags else "untagged"
    detail = (
        f"Vault: found proven examples for [{tag_label}]"
        if found
        else f"Vault: no proven examples yet for [{tag_label}]"
    )
    return ProgressEvent(
        job_id=job.job_id,
        stage="vault_retrieval",
        human_label="Checking vault for proven examples",
        pct=2,
        detail=detail,
    )


def _vault_write_event(job: Job, path: Path) -> ProgressEvent:
    """Build a visibility event for the run note that was just written."""
    return ProgressEvent(
        job_id=job.job_id,
        stage="vault_write",
        human_label="Saving learning note",
        pct=95,
        detail=f"Vault: saved run note {path.name}",
    )


def _tuning_diff_event(job: Job, tags: list[str], diff: dict) -> ProgressEvent:
    """Build a visibility event describing a vault tuning override.

    Surfaces *what* changed (and for which tags) in the activity stream, since
    this replaces an explicit "Proceed?" confirmation step - the run just
    proceeds with the learned tuning, and this event is how the user finds out.
    """
    tag_label = ", ".join(tags) if tags else "untagged"
    parts = [
        "rubric weights adjusted" if field == "rubric_weights" else f"{field} {old}→{new}"
        for field, (old, new) in diff.items()
    ]
    return ProgressEvent(
        job_id=job.job_id,
        stage="tuning",
        human_label="Applying learned tuning",
        pct=5,
        detail=f"Learned tuning for [{tag_label}]: " + "; ".join(parts),
    )


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

    # JD tagging always runs - the run note needs the role/domains split
    # regardless of the learning toggle. classify_jd_type never raises
    # (JdClassification(role=None, domains=[]) on failure).
    vault_settings = VaultSettings.load()
    classification = classify_jd_type(job.jd_raw)
    job.role = classification.role
    job.domains = classification.domains
    _db_set_classification(job, manager, job.role, job.domains)

    # Retrieval + tuning-override resolution are opt-out via job.obsidian_learn.
    # A vault error here must never fail the run - fall back to no examples and
    # the explicit/default tuning, exactly like the learning-off path.
    proven_examples: str | None = None
    tuning = job.tuning
    if job.obsidian_learn:
        try:
            proven_examples = retrieve_examples(
                classification.role, classification.domains, settings=vault_settings
            )
            if vault_settings.enabled:
                manager._emit(
                    job, _vault_retrieval_event(job, classification, found=proven_examples is not None)
                )
            # Loop B UNCHANGED: resolve_tuning still takes one flat list.
            # combined_tags = [role, *domains].
            tuning, diff = resolve_tuning(classification.combined_tags, job.tuning, settings=vault_settings)
            if diff:
                manager._emit(job, _tuning_diff_event(job, classification.combined_tags, diff))
        except Exception:
            log.exception("Vault retrieval/tuning failed for job %s - continuing without", job.job_id)
            proven_examples, tuning = None, job.tuning

    # Forward the per-application tuning only when set - a None config keeps the
    # call shape (and the pipeline's default behaviour) exactly as before.
    extra: dict = {}
    if tuning is not None:
        extra["tuning"] = tuning
    if job.bullet_shapes is not None:
        extra["bullet_shapes"] = job.bullet_shapes
    if proven_examples is not None:
        extra["proven_examples"] = proven_examples

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
                skills=job.models.skills.model,
                effort_fast=job.models.parser.effort,
                effort_strong=job.models.writer.effort,
                effort_gap=job.models.gap.effort,
                effort_scoring=job.models.scoring.effort,
                effort_skills=job.models.skills.effort,
                temp_fast=job.models.parser.temperature,
                temp_strong=job.models.writer.temperature,
                temp_gap=job.models.gap.temperature,
                temp_scoring=job.models.scoring.temperature,
                temp_skills=job.models.skills.temperature,
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

    # Always write the run note - a vault error here must never fail the run.
    try:
        note_path = write_run_note(
            job, final_state, classification.role, classification.domains, settings=vault_settings
        )
        if note_path is not None:
            manager._emit(job, _vault_write_event(job, note_path))
    except Exception:
        log.exception("Failed to write vault run note for job %s", job.job_id)

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


def _db_set_classification(
    job: "Job",
    manager: "JobManager",
    role: str | None,
    domains: list[str],
) -> None:
    """Persist the JD role/domain classification (best-effort).

    Written as soon as it's computed - before the pipeline runs - so the
    classification survives even if the run subsequently fails.
    """
    try:
        manager._repo.set_classification(job.job_id, role, domains)
    except Exception:
        log.exception("Failed to persist classification for job %s", job.job_id)


def _db_save_artifacts(
    job: "Job",
    manager: "JobManager",
) -> None:
    """Upload PDF to Storage (when configured) and persist artifacts to the repo.

    The storage upload is isolated from the artifact save (a failed upload never
    blocks it). The artifact save and the terminal "done" status are written in
    a single repository call so the row can never be left with artifacts saved
    but status stuck at "running" - one write succeeds or fails atomically.
    Storage is the durable home for the PDF; ``job.output_pdf`` points at the
    compiler's temp PDF (no local out/ copy is made), which is deleted after
    this function returns regardless of upload outcome.
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

    # Step 2 — save artifacts and mark done atomically (best-effort as a whole;
    # if this fails the row correctly stays "running" for mark_interrupted_running
    # to recover on the next restart, rather than landing in a half-done state).
    try:
        manager._repo.save_artifacts(
            job.job_id,
            best_latex=job.best_latex,
            output_skills=job.output_skills,
            score_report=job.score_report,
            aggregate_score=job.aggregate_score,
            passed=job.passed,
            pdf_object_key=pdf_object_key or job.pdf_object_key,
            status="done",
            finished_at=job.finished_at,
        )
    except Exception:
        log.exception("Failed to save artifacts for job %s", job.job_id)


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
