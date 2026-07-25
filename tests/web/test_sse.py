"""Phase 9 RED tests - SSE event_stream async generator."""
from __future__ import annotations

import asyncio

import pytest

from src.web.job import Job
from src.web.schemas import ProgressEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(job_id: str = "j1", stage: str = "writer") -> ProgressEvent:
    return ProgressEvent(
        job_id=job_id, stage=stage, human_label="Writing", pct=30, iteration=1,
    )


def _make_job() -> Job:
    job = Job(label="test")
    job.subscribers = set()
    return job


def _emit(job: Job, event: ProgressEvent) -> ProgressEvent:
    """Stamp seq via the buffer and fan out to live subscribers - mirrors JobManager._emit."""
    job.events.append(event)
    for q in list(job.subscribers):
        q.put_nowait(event)
    return event


# ---------------------------------------------------------------------------
# Test 1: yields buffered + live events in order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_yields_buffered_and_live_events():
    from src.web.sse import event_stream

    job = _make_job()
    job.events.append(_make_event(stage="parse_resume"))
    job.events.append(_make_event(stage="writer"))

    async def push_later():
        await asyncio.sleep(0.05)
        _emit(job, _make_event(stage="done"))

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

    async def push_done():
        await asyncio.sleep(0.05)
        _emit(job, _make_event(stage="done"))

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

    async def push_done():
        await asyncio.sleep(0.02)
        _emit(job, _make_event(stage="done"))

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

    # Cancel the consuming task - the finally block inside event_stream must run
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Give event loop a tick to flush the finally block
    await asyncio.sleep(0.02)
    assert len(job.subscribers) == 0


# ---------------------------------------------------------------------------
# Test 5: terminal already in the buffer must end the stream (no hang)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stops_when_terminal_already_buffered():
    """Reconnecting after a stop/fail must not hang waiting for a live event.

    Regression: event_stream used to replay a buffered ``failed``/``done`` and
    then block forever on the subscriber queue, leaving the UI stuck on
    ``Stopping…`` even though the job was already terminal.
    """
    from src.web.sse import event_stream

    job = _make_job()
    job.events.append(_make_event(stage="writer"))
    job.events.append(
        ProgressEvent(
            job_id="j1",
            stage="failed",
            human_label="Stopped",
            pct=0,
            iteration=1,
            error="You stopped this run before it finished.",
        )
    )

    results = []

    async def collect():
        async for event in event_stream(job, last_event_id=0):
            results.append(event)

    await asyncio.wait_for(collect(), timeout=1.0)

    assert [r.stage for r in results] == ["writer", "failed"]


# ---------------------------------------------------------------------------
# Test 6: event emitted during replay is not lost (subscribe-before-replay)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_emitted_during_replay_is_not_lost():
    """A terminal that lands while replaying must still reach the client.

    Subscribe-before-replay + seq dedupe closes the classic window where an
    event is appended after ``since()`` returns but before ``subscribers.add``.
    """
    from src.web.sse import event_stream

    job = _make_job()
    for _ in range(50):
        job.events.append(_make_event(stage="writer"))

    failed = ProgressEvent(
        job_id="j1",
        stage="failed",
        human_label="Stopped",
        pct=0,
        iteration=1,
        error="You stopped this run before it finished.",
    )

    results = []

    async def collect():
        async for event in event_stream(job, last_event_id=0):
            results.append(event)

    task = asyncio.ensure_future(collect())
    # Land the terminal while the generator is still replaying the buffer.
    await asyncio.sleep(0)
    _emit(job, failed)

    await asyncio.wait_for(task, timeout=1.0)

    assert results[-1].stage == "failed"
    # Deduped - the failed frame must appear exactly once even though it was
    # both buffered and queued.
    assert sum(1 for r in results if r.stage == "failed") == 1
