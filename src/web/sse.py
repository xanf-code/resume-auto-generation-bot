"""SSE async generator for streaming job progress events to HTTP clients.

``event_stream`` replays buffered events (for reconnecting clients using
Last-Event-ID) then yields live events pushed by ``JobManager._emit`` via
per-subscriber asyncio.Queue objects.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from src.web.job import Job
from src.web.schemas import ProgressEvent

_TERMINAL = frozenset({"done", "failed"})


async def event_stream(
    job: Job,
    last_event_id: int = 0,
) -> AsyncGenerator[ProgressEvent, None]:
    """Async generator yielding ProgressEvent objects for SSE delivery.

    Subscribes *before* replaying the buffer so an event emitted between the
    buffer scan and queue registration cannot vanish. Replayed frames that also
    land on the live queue are skipped by seq. Stops cleanly on a terminal
    stage (done/failed), including when that terminal is already buffered -
    reconnecting after a user abort must not hang waiting for another frame.
    The subscriber queue is always removed in the finally block - even on
    cancel or client disconnect.
    """
    q: asyncio.Queue[ProgressEvent] = asyncio.Queue()
    # Subscribe first so anything emitted during replay also reaches *q*.
    job.subscribers.add(q)
    try:
        last_sent = last_event_id

        for event in job.events.since(last_sent):
            yield event
            last_sent = event.seq
            if event.stage in _TERMINAL:
                return

        while True:
            event = await q.get()
            # Already delivered via the buffer replay above.
            if event.seq <= last_sent:
                continue
            yield event
            last_sent = event.seq
            if event.stage in _TERMINAL:
                break
    finally:
        job.subscribers.discard(q)
