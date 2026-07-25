"""Job model and event buffer for the web layer.

``Job`` carries all mutable runtime state for a single pipeline run.
``EventBuffer`` is the bounded replay buffer that backs SSE re-subscription.
Both are pure data structures - no threading or HTTP concerns here.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.pipeline.tuning import PipelineTuning
from src.web.schemas import JobStatus


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

    # Pipeline artifacts (populated on completion)
    best_latex: str | None = None
    output_pdf: str | None = None
    output_skills: str | None = None
    score_report_md: str | None = None
    aggregate_score: float | None = None
    passed: bool | None = None

    # Per-job SSE replay buffer (set by job_manager at creation)
    events: EventBuffer = field(default_factory=lambda: EventBuffer(maxlen=500))

    # Live SSE subscribers - each is an asyncio.Queue owned by one SSE connection
    subscribers: set[asyncio.Queue] = field(default_factory=set)

    # Cooperative cancellation. Set from the request thread (via JobManager.cancel);
    # read by the worker thread's on_step callback, which aborts at the next node
    # boundary. A threading.Event is the safe cross-thread signalling primitive.
    cancel_event: threading.Event = field(default_factory=threading.Event)
