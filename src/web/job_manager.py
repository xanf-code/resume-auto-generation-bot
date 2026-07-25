"""JobManager - registry + ThreadPoolExecutor for pipeline runs.

All pipeline execution happens in worker threads (never on the async event
loop) because ``src/agents/recruiters.py`` calls ``asyncio.run()`` inside a
LangGraph node, which would raise RuntimeError if an event loop were already
running in that thread.

The sync→async bridge: worker threads call ``_emit``, which uses
``loop.call_soon_threadsafe`` to push events into per-subscriber asyncio.Queue
objects without touching the event loop from outside the loop thread.

Persistence is write-through: if a ``ResumeRepository`` is configured all
lifecycle state changes are mirrored to Supabase.  Failures are logged but
never propagated — the in-memory state is always authoritative.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from src.web.config import WebSettings
from src.web.job import Job
from src.web.schemas import JobStatus, JobSubmitRequest, ProgressEvent
from src.web.runner import run_job

if TYPE_CHECKING:
    from src.db.repository import ResumeRepository

log = logging.getLogger(__name__)


class JobManager:
    """Manages job lifecycle: submission, registry, concurrency, and SSE fan-out."""

    def __init__(
        self,
        settings: WebSettings,
        repo: "ResumeRepository | None" = None,
    ) -> None:
        self.settings = settings
        self._registry: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._repo: "ResumeRepository | None" = repo

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running async event loop so ``_emit`` can bridge threads."""
        self._loop = loop

    def submit(self, req: JobSubmitRequest) -> Job:
        """Create a Job, register it, enqueue it in the thread pool, return immediately."""
        job = Job(
            label=req.label,
            status=JobStatus.QUEUED,
        )
        job.resume_tex_raw = req.resume_tex
        job.jd_raw = req.jd_text
        job.jd_name = req.label
        job.enable_scoring = req.enable_scoring
        job.tuning = req.tuning.to_tuning() if req.tuning is not None else None
        job.models = (
            req.models.to_pipeline_models() if req.models is not None else None
        )
        job.bullet_shapes = req.bullet_shapes
        job.out_dir = f"{self.settings.out_root}/{job.job_id}"

        self._registry[job.job_id] = job

        # Write-through: persist the new job record to Supabase.
        if self._repo is not None:
            try:
                from src.db.models import JobRecord
                record = JobRecord(
                    job_id=job.job_id,
                    label=job.label,
                    status="queued",
                    created_at=job.created_at,
                    resume_tex_raw=job.resume_tex_raw,
                    jd_raw=job.jd_raw,
                    jd_name=job.jd_name,
                    enable_scoring=job.enable_scoring,
                    tuning=req.tuning.model_dump() if req.tuning is not None else None,
                    models=req.models.model_dump() if req.models is not None else None,
                    bullet_shapes=job.bullet_shapes,
                )
                self._repo.create(record)
            except Exception:
                log.exception("Failed to persist job %s to Supabase", job.job_id)

        self._executor.submit(run_job, job, self)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._registry.get(job_id)

    def list(self) -> list[Job]:
        return list(self._registry.values())

    def rename(self, job_id: str, label: str) -> Job | None:
        """Update the display label. Returns None if the job is missing."""
        job = self._registry.get(job_id)
        if job is None:
            return None
        job.label = label
        if self._repo is not None:
            try:
                self._repo.rename(job_id, label)
            except Exception:
                log.exception("Failed to rename job %s in Supabase", job_id)
        return job

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a running or queued job.

        Sets the job's cancel event; the worker thread's ``on_step`` callback
        observes it and aborts at the next node boundary (an in-flight LLM call
        finishes first - Python threads can't be force-killed). Emits an
        immediate progress ack so the UI can leave a frozen "Stopping…" state
        and show that the stop was heard. Returns False if the job is missing
        or already in a terminal state.
        """
        job = self._registry.get(job_id)
        if job is None:
            return False
        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            return False
        # Idempotent for a second click while already winding down.
        if job.cancel_event.is_set():
            return True
        job.cancel_event.set()
        prior = job.events.since(0)
        last = prior[-1] if prior else None
        self._emit(
            job,
            ProgressEvent(
                job_id=job.job_id,
                stage=last.stage if last else "init",
                human_label="Stopping…",
                pct=last.pct if last else 0,
                iteration=last.iteration if last else 1,
                detail="Stop requested — finishing the current step, then winding down.",
            ),
        )
        return True

    def delete(self, job_id: str) -> bool:
        """Remove a job from the registry, delete on-disk artifacts, and Supabase records.

        Returns False if the job was not found. A running pipeline may still
        finish in the pool afterward; its writes land on a removed directory.
        """
        job = self._registry.pop(job_id, None)
        if job is None:
            return False
        if job.out_dir:
            shutil.rmtree(job.out_dir, ignore_errors=True)
        if self._repo is not None:
            try:
                from src.db.storage import delete_prefix
                from src.web.config import _optional_db_settings
                from src.db.client import get_client
                db_settings = _optional_db_settings()
                if db_settings is not None:
                    delete_prefix(job_id, get_client(db_settings), db_settings.bucket)
                self._repo.delete(job_id)
            except Exception:
                log.exception("Failed to delete job %s from Supabase", job_id)
        return True

    def _emit(self, job: Job, event: ProgressEvent) -> None:
        """Append event to the replay buffer and fan-out to all live subscribers.

        Safe to call from any thread: queue put is done via call_soon_threadsafe
        so it's dispatched onto the event-loop thread.
        """
        job.events.append(event)
        if self._loop is not None:
            for q in list(job.subscribers):
                self._loop.call_soon_threadsafe(q.put_nowait, event)
