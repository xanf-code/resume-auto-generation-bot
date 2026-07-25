"""JobManager — registry + ThreadPoolExecutor for pipeline runs.

All pipeline execution happens in worker threads (never on the async event
loop) because ``src/agents/recruiters.py`` calls ``asyncio.run()`` inside a
LangGraph node, which would raise RuntimeError if an event loop were already
running in that thread.

The sync→async bridge: worker threads call ``_emit``, which uses
``loop.call_soon_threadsafe`` to push events into per-subscriber asyncio.Queue
objects without touching the event loop from outside the loop thread.
"""
from __future__ import annotations

import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor

from src.web.config import WebSettings
from src.web.job import Job
from src.web.schemas import JobStatus, JobSubmitRequest, ProgressEvent
from src.web.runner import run_job


class JobManager:
    """Manages job lifecycle: submission, registry, concurrency, and SSE fan-out."""

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self._registry: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
        self._loop: asyncio.AbstractEventLoop | None = None

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
        job.out_dir = f"{self.settings.out_root}/{job.job_id}"

        self._registry[job.job_id] = job
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
        return job

    def delete(self, job_id: str) -> bool:
        """Remove a job from the registry and delete its on-disk artifacts.

        Returns False if the job was not found. A running pipeline may still
        finish in the pool afterward; its writes land on a removed directory.
        """
        job = self._registry.pop(job_id, None)
        if job is None:
            return False
        if job.out_dir:
            shutil.rmtree(job.out_dir, ignore_errors=True)
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
