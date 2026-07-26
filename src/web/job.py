"""Job model and event buffer for the web layer.

``Job`` carries mutable runtime state for a single pipeline run (SSE buffer,
cancel signal, worker fields). Durable job data lives in the repository;
``job_from_record`` maps a persisted ``JobRecord`` into a read view for HTTP.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.pipeline.models import PipelineModels
from src.pipeline.tuning import PipelineTuning
from src.web.schemas import JobStatus

if TYPE_CHECKING:
    from src.db.models import JobRecord


class EventBuffer:
    """Bounded FIFO of ProgressEvent objects with monotonic sequence numbers.

    ``append`` stamps the event's ``.seq`` attribute and returns the assigned
    sequence number.  ``since(seq)`` yields all events with seq > the given
    value, enabling SSE replay from ``Last-Event-ID``.
    """

    def __init__(self, maxlen: int) -> None:
        self._buf: deque[Any] = deque(maxlen=maxlen)
        self._next_seq: int = 0

    def append(self, event: Any) -> int:
        self._next_seq += 1
        event.seq = self._next_seq
        self._buf.append(event)
        return self._next_seq

    def since(self, seq: int) -> list[Any]:
        return [e for e in self._buf if e.seq > seq]

    def __len__(self) -> int:
        return len(self._buf)


@dataclass
class Job:
    """All state for a single pipeline run."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    # Pipeline input (set by job_manager at submission)
    resume_tex_raw: str = ""
    jd_raw: str = ""
    jd_name: str = ""
    enable_scoring: bool = False
    out_dir: str = ""
    # Per-application pipeline tuning. None → the pipeline uses its defaults
    # (config.settings constants).
    tuning: PipelineTuning | None = None
    # Per-application model overrides. None → config.settings MODEL_* defaults.
    models: PipelineModels | None = None
    # Per-résumé bullet shape selection. None → default rotation over all four.
    bullet_shapes: list[str] | None = None

    # Pipeline artifacts (populated on completion; persisted to the repository)
    best_latex: str | None = None
    output_pdf: str | None = None          # local path used only for the Storage upload
    score_report_md: str | None = None
    aggregate_score: float | None = None
    passed: bool | None = None
    # JSON artifacts — durable copy lives in the repository; runtime holds the
    # in-flight copy until the worker finishes writing.
    score_report: dict | None = None
    output_skills: dict | None = None
    # Supabase Storage object key for the compiled PDF, set after upload.
    # GET /jobs/{id}/pdf streams bytes from Storage using this key.
    pdf_object_key: str | None = None

    # Per-job SSE replay buffer (ephemeral — not persisted)
    events: EventBuffer = field(default_factory=lambda: EventBuffer(maxlen=500))

    # Live SSE subscribers - each is an asyncio.Queue owned by one SSE connection
    subscribers: set[asyncio.Queue] = field(default_factory=set)

    # Cooperative cancellation. Set from the request thread (via JobManager.cancel);
    # read by the worker thread's on_step callback, which aborts at the next node
    # boundary. A threading.Event is the safe cross-thread signalling primitive.
    cancel_event: threading.Event = field(default_factory=threading.Event)


def job_from_record(rec: "JobRecord", *, event_buffer_max: int = 500) -> Job:
    """Build a ``Job`` read view from a persisted ``JobRecord``.

    Does not restore SSE subscribers or cancel state — those exist only in the
    ephemeral runtime map for active runs.
    """
    return Job(
        job_id=rec.job_id,
        label=rec.label,
        status=JobStatus(rec.status),
        created_at=rec.created_at,
        started_at=rec.started_at,
        finished_at=rec.finished_at,
        error=rec.error,
        resume_tex_raw=rec.resume_tex_raw,
        jd_raw=rec.jd_raw,
        jd_name=rec.jd_name,
        enable_scoring=rec.enable_scoring,
        bullet_shapes=rec.bullet_shapes,
        best_latex=rec.best_latex,
        aggregate_score=rec.aggregate_score,
        passed=rec.passed,
        score_report=rec.score_report,
        output_skills=rec.output_skills,
        pdf_object_key=rec.pdf_object_key,
        events=EventBuffer(maxlen=event_buffer_max),
    )
