"""Phase 9 RED tests — JobManager lifecycle, failure propagation, concurrency cap."""
from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import patch

import pytest

import src.web.runner as runner_module
from src.web.config import WebSettings
from src.web.schemas import JobStatus, JobSubmitRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**kwargs) -> WebSettings:
    defaults = dict(max_concurrent_jobs=3, out_root="/tmp/resumebot_test", event_buffer_max=500)
    defaults.update(kwargs)
    return WebSettings(**defaults)


def _make_req(**kwargs) -> JobSubmitRequest:
    defaults = dict(label="TestJob", resume_tex="\\documentclass{article}", jd_text="Engineer role")
    defaults.update(kwargs)
    return JobSubmitRequest(**defaults)


def _wait_for(condition, timeout: float = 5.0, poll: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(poll)
    return False


def _fake_pipeline_factory(on_step_calls: int = 2, final_state: dict | None = None, raise_exc=None):
    """Return a fake stream_pipeline that calls on_step N times then returns final_state."""
    if final_state is None:
        final_state = {
            "best_latex": "\\documentclass{article}",
            "aggregate_score": 85.0,
            "passed": True,
            "output_pdf": "out/j/resume.pdf",
        }

    def fake_pipeline(resume_tex_raw, jd_raw, out_dir, jd_name, enable_scoring, on_step=None):
        if raise_exc is not None:
            raise raise_exc
        for i in range(on_step_calls):
            if on_step:
                on_step({"writer_output": f"step{i}"}, {"iteration": 1, **final_state})
        return final_state

    return fake_pipeline


# ---------------------------------------------------------------------------
# Test 1: happy-path lifecycle
# ---------------------------------------------------------------------------

def test_lifecycle():
    from src.web.job_manager import JobManager

    settings = _make_settings()
    manager = JobManager(settings)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    manager.bind_loop(loop)

    fake = _fake_pipeline_factory(on_step_calls=2)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake):
        req = _make_req()
        job = manager.submit(req)

        assert job.job_id
        assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.DONE)

        finished = _wait_for(lambda: job.status == JobStatus.DONE, timeout=10.0)
        assert finished, f"Job did not reach DONE; status={job.status}, error={job.error}"

    assert job.best_latex is not None
    assert job.aggregate_score == 85.0
    assert len(job.events) >= 2

    loop.call_soon_threadsafe(loop.stop)


# ---------------------------------------------------------------------------
# Test 2: failure propagates
# ---------------------------------------------------------------------------

def test_failure_propagates():
    from src.web.job_manager import JobManager

    settings = _make_settings()
    manager = JobManager(settings)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    manager.bind_loop(loop)

    fake = _fake_pipeline_factory(raise_exc=RuntimeError("oops"))

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake):
        job = manager.submit(_make_req())
        finished = _wait_for(lambda: job.status in (JobStatus.DONE, JobStatus.FAILED), timeout=10.0)

    assert finished
    assert job.status == JobStatus.FAILED
    assert "oops" in (job.error or "")

    loop.call_soon_threadsafe(loop.stop)


# ---------------------------------------------------------------------------
# Test 3: GraphRecursionError yields friendly message
# ---------------------------------------------------------------------------

def test_graph_recursion_error_friendly_message():
    from src.web.job_manager import JobManager

    class GraphRecursionError(Exception):
        pass

    settings = _make_settings()
    manager = JobManager(settings)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    manager.bind_loop(loop)

    fake = _fake_pipeline_factory(raise_exc=GraphRecursionError("too many steps"))

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake):
        job = manager.submit(_make_req())
        finished = _wait_for(lambda: job.status == JobStatus.FAILED, timeout=10.0)

    assert finished
    assert job.status == JobStatus.FAILED
    assert "recursion limit" in (job.error or "").lower()

    loop.call_soon_threadsafe(loop.stop)


# ---------------------------------------------------------------------------
# Test 4: concurrency cap — exactly max_workers run at once
# ---------------------------------------------------------------------------

def test_concurrency_cap():
    from src.web.job_manager import JobManager

    MAX = 2
    settings = _make_settings(max_concurrent_jobs=MAX)
    manager = JobManager(settings)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    manager.bind_loop(loop)

    gate = threading.Event()
    running_count = threading.Semaphore(0)

    def blocking_pipeline(resume_tex_raw, jd_raw, out_dir, jd_name, enable_scoring, on_step=None):
        running_count.release()
        gate.wait(timeout=30)
        return {"best_latex": "x", "aggregate_score": 80.0, "passed": True, "output_pdf": "x.pdf"}

    jobs = []
    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=blocking_pipeline):
        for i in range(4):
            jobs.append(manager.submit(_make_req(label=f"job{i}")))

        # Wait until exactly MAX workers have started
        started = 0
        deadline = time.monotonic() + 5.0
        while started < MAX and time.monotonic() < deadline:
            if running_count.acquire(timeout=0.1):
                started += 1

        # Give scheduler a moment to potentially start a 3rd (it shouldn't)
        time.sleep(0.3)

        running = sum(1 for j in jobs if j.status == JobStatus.RUNNING)
        queued = sum(1 for j in jobs if j.status == JobStatus.QUEUED)

        assert running == MAX, f"Expected {MAX} RUNNING, got {running}"
        assert queued == 4 - MAX, f"Expected {4 - MAX} QUEUED, got {queued}"

        gate.set()

        all_done = _wait_for(lambda: all(j.status == JobStatus.DONE for j in jobs), timeout=15.0)
        assert all_done, [j.status for j in jobs]

    loop.call_soon_threadsafe(loop.stop)


# ---------------------------------------------------------------------------
# Test 5: one failure doesn't affect another job
# ---------------------------------------------------------------------------

def test_other_jobs_unaffected_by_failure():
    from src.web.job_manager import JobManager

    settings = _make_settings(max_concurrent_jobs=2)
    manager = JobManager(settings)

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    manager.bind_loop(loop)

    call_count = [0]
    lock = threading.Lock()

    def alternating_pipeline(resume_tex_raw, jd_raw, out_dir, jd_name, enable_scoring, on_step=None):
        with lock:
            idx = call_count[0]
            call_count[0] += 1
        if idx == 0:
            raise RuntimeError("deliberate failure")
        return {"best_latex": "ok", "aggregate_score": 90.0, "passed": True, "output_pdf": "ok.pdf"}

    jobs = []
    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=alternating_pipeline):
        for i in range(2):
            jobs.append(manager.submit(_make_req(label=f"job{i}")))

        all_terminal = _wait_for(
            lambda: all(j.status in (JobStatus.DONE, JobStatus.FAILED) for j in jobs),
            timeout=15.0,
        )
        assert all_terminal

    statuses = {j.status for j in jobs}
    assert JobStatus.DONE in statuses, "Expected at least one DONE job"
    assert JobStatus.FAILED in statuses, "Expected at least one FAILED job"

    loop.call_soon_threadsafe(loop.stop)


# ---------------------------------------------------------------------------
# Test 6: rename + delete
# ---------------------------------------------------------------------------

def test_rename_and_delete(tmp_path):
    from src.web.job import Job
    from src.web.job_manager import JobManager

    manager = JobManager(_make_settings(out_root=str(tmp_path)))
    job = Job(label="Old", status=JobStatus.DONE)
    out = tmp_path / job.job_id
    out.mkdir()
    (out / "artifact.txt").write_text("keep")
    job.out_dir = str(out)
    manager._registry[job.job_id] = job

    renamed = manager.rename(job.job_id, "New Name")
    assert renamed is not None
    assert renamed.label == "New Name"
    assert manager.rename("missing", "x") is None

    assert manager.delete(job.job_id) is True
    assert manager.get(job.job_id) is None
    assert not out.exists()
    assert manager.delete(job.job_id) is False
