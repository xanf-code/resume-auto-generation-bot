"""JobManager - repository-backed CRUD + ThreadPoolExecutor for pipeline runs.

All pipeline execution happens in worker threads (never on the async event
loop) because ``src/agents/recruiters.py`` calls ``asyncio.run()`` inside a
LangGraph node, which would raise RuntimeError if an event loop were already
running in that thread.

The sync→async bridge: worker threads call ``_emit``, which uses
``loop.call_soon_threadsafe`` to push events into per-subscriber asyncio.Queue
objects without touching the event loop from outside the loop thread.

Durable job state lives exclusively in ``ResumeRepository`` (Supabase or the
in-memory stand-in).  ``_runtime`` holds only ephemeral live-run concerns:
SSE buffers, subscribers, and cancel signals.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol

from src.db.models import JobRecord
from src.web.config import WebSettings
from src.web.job import Job, job_from_record
from src.web.schemas import JobStatus, JobSubmitRequest, ProgressEvent
from src.web.runner import run_job

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class JobRepository(Protocol):
    """Minimal repository surface used by JobManager."""

    def create(self, record: JobRecord) -> None: ...
    def get(self, job_id: str) -> JobRecord | None: ...
    def list(self) -> list[JobRecord]: ...
    def set_status(
        self,
        job_id: str,
        status: str,
        *,
        started_at: Any = None,
        finished_at: Any = None,
        error: str | None = None,
    ) -> None: ...
    def save_artifacts(self, job_id: str, **kwargs: Any) -> None: ...
    def rename(self, job_id: str, label: str) -> JobRecord | None: ...
    def delete(self, job_id: str) -> bool: ...
    def mark_interrupted_running(self) -> int: ...


class JobManager:
    """Manages job lifecycle: repository CRUD, concurrency, and SSE fan-out."""

    def __init__(
        self,
        settings: WebSettings,
        repo: JobRepository,
    ) -> None:
        self.settings = settings
        self._repo: JobRepository = repo
        # Ephemeral live-run state only — never the source of truth for CRUD.
        self._runtime: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running async event loop so ``_emit`` can bridge threads."""
        self._loop = loop

    def submit(self, req: JobSubmitRequest) -> Job:
        """Persist a new job, register ephemeral runtime, enqueue the worker."""
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
        job.obsidian_learn = req.obsidian_learn
        job.out_dir = f"{self.settings.out_root}/{job.job_id}"

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
        # Repository first — fail the request if persistence fails.
        self._repo.create(record)

        self._runtime[job.job_id] = job
        self._executor.submit(run_job, job, self)
        return job

    def get(self, job_id: str) -> Job | None:
        """Return a job read view from the repository (source of truth)."""
        rec = self._repo.get(job_id)
        if rec is None:
            return None
        return job_from_record(rec, event_buffer_max=self.settings.event_buffer_max)

    def get_runtime(self, job_id: str) -> Job | None:
        """Return the ephemeral live-run handle, if any."""
        return self._runtime.get(job_id)

    def list(self) -> list[Job]:
        """Return all jobs from the repository, newest first."""
        return [
            job_from_record(rec, event_buffer_max=self.settings.event_buffer_max)
            for rec in self._repo.list()
        ]

    def rename(self, job_id: str, label: str) -> Job | None:
        """Update the display label in the repository. Returns None if missing."""
        rec = self._repo.rename(job_id, label)
        if rec is None:
            return None
        rt = self._runtime.get(job_id)
        if rt is not None:
            rt.label = label
        return job_from_record(rec, event_buffer_max=self.settings.event_buffer_max)

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a running or queued job.

        Uses repository status as authority.  If a runtime handle exists, sets
        its cancel event so the worker aborts at the next node boundary.  If
        there is no runtime (e.g. after a restart before mark_interrupted),
        marks the row failed directly in the repository.
        """
        rec = self._repo.get(job_id)
        if rec is None:
            return False
        if rec.status not in ("queued", "running"):
            return False

        job = self._runtime.get(job_id)
        if job is None:
            from datetime import datetime, timezone
            self._repo.set_status(
                job_id,
                "failed",
                finished_at=datetime.now(timezone.utc),
                error="You stopped this run before it finished.",
            )
            return True

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
        """Remove a job from the repository, runtime, disk, and Storage.

        Returns False if the job was not found in the repository.
        """
        if self._repo.get(job_id) is None:
            return False

        job = self._runtime.pop(job_id, None)
        out_dir = (
            job.out_dir
            if job is not None and job.out_dir
            else f"{self.settings.out_root}/{job_id}"
        )
        if out_dir:
            shutil.rmtree(out_dir, ignore_errors=True)

        try:
            from src.db.storage import delete_prefix
            from src.web.config import _optional_db_settings
            from src.db.client import get_client
            db_settings = _optional_db_settings()
            if db_settings is not None:
                delete_prefix(job_id, get_client(db_settings), db_settings.bucket)
        except Exception:
            log.exception("Failed to delete Storage objects for job %s", job_id)

        try:
            self._repo.delete(job_id)
        except Exception:
            log.exception("Failed to delete job %s from repository", job_id)
            return False
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
