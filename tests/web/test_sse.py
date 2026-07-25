"""Phase 9 RED tests — SSE event_stream async generator."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone

import pytest

from src.web.job import EventBuffer, Job
from src.web.schemas import JobStatus, ProgressEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(job_id: str = "j1", stage: str = "writer", seq: int = 0) -> ProgressEvent:
    return ProgressEvent(job_id=job_id, stage=stage, human_label="Writing", pct=30, iteration=1, seq=seq)


def _make_job() -> Job:
    job = Job(label="test")
    job.subscribers = set()
    return job


async def _collect(gen, limit: int = 20) -> list[ProgressEvent]:
    results = []
    async for event in gen:
        results.append(event)
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# Test 1: yields buffered + live events in order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_yields_buffered_and_live_events():
    from src.web.sse import event_stream

    job = _make_job()

    e1 = _make_event(stage="parse_resume")
    e2 = _make_event(stage="writer")
    job.events.append(e1)
    job.events.append(e2)

    # Push a live event after the generator starts
    live_event = _make_event(stage="done")

    async def push_later():
        await asyncio.sleep(0.05)
        for q in list(job.subscribers):
            q.put_nowait(live_event)

    gen = event_stream(job, last_event_id=0)
    task = asyncio.ensure_future(push_later())

    results = []
    async for event in gen:
        results.append(event)
        if event.stage == "done":
            break

    await task

    assert len(results) == 3
    assert results[0].stage == "parse_resume"
    assert results[1].stage == "writer"
    assert results[2].stage == "done"


# ---------------------------------------------------------------------------
# Test 2: Last-Event-ID replay skips already-seen events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_last_event_id_replay():
    from src.web.sse import event_stream

    job = _make_job()

    stages = ["parse_resume", "analyze_jd", "gap_analysis", "generate_skills", "writer"]
    for s in stages:
        job.events.append(_make_event(stage=s))

    # Seqs 1-5, last_event_id=3 → should only replay seqs 4 and 5
    done_event = _make_event(stage="done")

    async def push_done():
        await asyncio.sleep(0.05)
        for q in list(job.subscribers):
            q.put_nowait(done_event)

    gen = event_stream(job, last_event_id=3)
    task = asyncio.ensure_future(push_done())

    results = []
    async for event in gen:
        results.append(event)
        if event.stage == "done":
            break

    await task

    # First two should be seqs 4 and 5 (generate_skills, writer)
    replayed = [r for r in results if r.stage != "done"]
    assert len(replayed) == 2
    assert replayed[0].stage == "generate_skills"
    assert replayed[1].stage == "writer"


# ---------------------------------------------------------------------------
# Test 3: generator exits cleanly on done event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stops_on_done_event():
    from src.web.sse import event_stream

    job = _make_job()

    done_event = _make_event(stage="done")

    async def push_done():
        await asyncio.sleep(0.02)
        for q in list(job.subscribers):
            q.put_nowait(done_event)

    gen = event_stream(job, last_event_id=0)
    task = asyncio.ensure_future(push_done())

    results = []
    async for event in gen:
        results.append(event)
        # generator should self-terminate after done

    await task

    assert len(results) == 1
    assert results[0].stage == "done"


# ---------------------------------------------------------------------------
# Test 4: subscriber removed in finally on task cancellation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscriber_removed_on_aclose():
    from src.web.sse import event_stream

    job = _make_job()

    async def drain_gen():
        async for _ in event_stream(job, last_event_id=0):
            pass

    task = asyncio.ensure_future(drain_gen())

    # Let the generator register itself as a subscriber
    await asyncio.sleep(0.05)
    assert len(job.subscribers) == 1

    # Cancel the consuming task — the finally block inside event_stream must run
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Give event loop a tick to flush the finally block
    await asyncio.sleep(0.02)
    assert len(job.subscribers) == 0
