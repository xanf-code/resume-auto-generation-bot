# Phase 9 — Job Manager, Runner, Sync→Async SSE Bridge

**Goal:** Run pipelines concurrently in a thread pool (bounded to `MAX_CONCURRENT_JOBS`), translate their streamed progress into `ProgressEvent`s, and deliver those events to async SSE subscribers safely across the thread boundary.

**Prereq:** Phase 8. **Blocks:** Phase 10.

## Why a thread pool (not asyncio)
`src/agents/recruiters.py:114` calls `asyncio.run(run_panel(state))` inside a node. Running `graph.stream()` on the server event loop → `RuntimeError: asyncio.run() cannot be called from a running event loop`. So pipelines run in worker threads with no ambient loop. One `ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)` is both the offloader and the concurrency cap.

## Modules
- `src/web/runner.py` — `run_job(job, manager)` sync body: try/except around `main.stream_pipeline(job.resume_tex_raw, job.jd_raw, out_dir=job.out_dir, jd_name=job.jd_name, enable_scoring=..., on_step=<closure>)`. The closure builds a `ProgressEvent` via `events.build_progress_event` and hands it to `manager._emit(job, event)`, and updates `job` snapshot fields. On success: snapshot `best_latex` onto `job` + write `out/{job_id}/best.tex`, resolve `output_pdf/report/skills` from `final_state`, status=`done`, emit terminal `done`. On exception: status=`failed`, friendly message for `GraphRecursionError` (mirror main.py:225), emit terminal `failed`.
- `src/web/job_manager.py` — `JobManager`: registry `dict[str,Job]`, `ThreadPoolExecutor(max_workers=...)`, `bind_loop(loop)` (called from app lifespan with `asyncio.get_running_loop()`), `submit(req)->Job`, `get(id)`, `list()`, and:
  ```python
  def _emit(self, job, event):
      job.events.append(event)                 # deque.append atomic under GIL
      for q in list(job.subscribers):           # snapshot before iterating
          self._loop.call_soon_threadsafe(q.put_nowait, event)
  ```
- `src/web/sse.py` — `event_stream(job, last_event_id)` async generator: create `asyncio.Queue`, replay `job.events.since(last_event_id)`, add queue to `job.subscribers`, loop `await q.get()` yielding until a `done`/`failed` event, `finally` discard the queue. Client disconnect cancels the generator (cleanup in `finally`) but does **not** cancel the running pipeline (paid work already in flight).

## TDD

### RED
- `tests/web/test_job_manager.py`: monkeypatch `src.main.stream_pipeline` with a fake calling `on_step` N times then returning a canned `final_state`.
  - lifecycle `queued→running→done`; events buffered; terminal `done` carries artifact paths.
  - raising fake → `failed` with clean `error`; `GraphRecursionError`-shaped → friendly message; other jobs unaffected.
  - **concurrency cap:** `MAX_CONCURRENT_JOBS=2`, submit 4 jobs whose fake blocks on a `threading.Event`; assert exactly 2 `running`/2 `queued`; release → all `done`.
- `tests/web/test_sse.py`: drive `event_stream` with a fake job — yields buffered+live events in order, stops after `done`; `Last-Event-ID=3` replays only seq>3; cancelling the generator mid-stream removes the subscriber queue (`finally`).

Tests need a bound loop: run the async parts under `pytest.mark.asyncio`; for `_emit` cross-thread delivery, capture the running loop in the test and `bind_loop` it.

### GREEN
Implement `runner.py`, `job_manager.py`, `sse.py`.

## Acceptance
`python3 -m pytest tests/web/test_job_manager.py tests/web/test_sse.py -q` passes, including the concurrency-cap test. No real LLM/tectonic invoked.

## Files
`src/web/{runner,job_manager,sse}.py`, `tests/web/{test_job_manager,test_sse}.py`.
