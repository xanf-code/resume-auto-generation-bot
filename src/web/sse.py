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


async def event_stream(
    job: Job,
    last_event_id: int = 0,
) -> AsyncGenerator[ProgressEvent, None]:
    """Async generator yielding ProgressEvent objects for SSE delivery.

    Replays all buffered events with seq > last_event_id, then registers as a
    live subscriber and yields events until a terminal stage (done/failed).
    The subscriber queue is always removed in the finally block — even on
    cancel or client disconnect.
    """
    q: asyncio.Queue[ProgressEvent] = asyncio.Queue()

    # Replay buffered events before registering for live ones so no events are
    # missed between the buffer read and queue registration.
    for event in job.events.since(last_event_id):
        yield event

    job.subscribers.add(q)
    try:
        while True:
            event = await q.get()
            yield event
            if event.stage in ("done", "failed"):
                break
    finally:
        job.subscribers.discard(q)
