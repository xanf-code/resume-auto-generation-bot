# Phase 10 — FastAPI Routers + App Factory

**Goal:** Expose the job manager and raw compile over HTTP + SSE. Add web dependencies.

**Prereq:** Phase 9. **Blocks:** Phases 11–12.

## Dependencies (append to `requirements.txt`)
`fastapi>=0.110`, `uvicorn[standard]>=0.29`, `sse-starlette>=2.1`. (No `python-multipart` — jobs submit as JSON strings.) Reuse existing `pydantic`, `pytest-asyncio`.

## Endpoints (base `/api`)
- `POST /api/jobs` — `JobSubmitRequest` → `202 JobSummary {job_id,label,status,created_at,events_url}`. Empty tex/jd → 422.
- `GET /api/jobs` — `{jobs: JobSummary[]}` newest first.
- `GET /api/jobs/{id}` — `JobDetail` (+ `artifacts` URLs when done); 404 unknown.
- `GET /api/jobs/{id}/events` — **SSE** via `sse-starlette` `EventSourceResponse`; frames set `id: <seq>`, `event: progress|done|failed`, JSON `data`; header `X-Accel-Buffering: no`; honors `Last-Event-ID`.
- `GET /api/jobs/{id}/latex` — `{latex}` (`best_latex`); 409 if not done.
- `GET /api/jobs/{id}/pdf?download=0|1` — streams `output_pdf`, `application/pdf`; 404 if none.
- `GET /api/jobs/{id}/skills` — structured `SkillDumpDTO` JSON (+`total`); `?format=mdx` streams `skills.mdx`.
- `GET /api/jobs/{id}/report` — parsed `score_report.json`.
- `POST /api/compile` — `{latex}` → runs `tectonic.compile_tex` in a **separate small pool** (editor spam must not starve real jobs); `200 application/pdf` or `422 CompileErrorResponse {ok:false,errors:[...]}`. No identity/page checks.
- `GET /api/healthz` — `{status, api_key_present, active_jobs, max_concurrent}` (never leak the key).

## App factory — `src/web/app.py`
`create_app()`: build `JobManager`, include routers, CORS (dev origin), lifespan `bind_loop(asyncio.get_running_loop())` on startup + pool shutdown on close. Prod static mount of `frontend/dist` is added in Phase 12 (after routes, SPA fallback).

## TDD

### RED — `httpx.AsyncClient` + `ASGITransport` against `create_app()`, pipeline/compile monkeypatched
- `tests/web/test_routes_jobs.py`: `POST /api/jobs` → 202 shape; empty tex/jd → 422; list/detail shapes + 404; seed a done job under a `tmp_path` `OUT_ROOT` → `/latex` returns `best_latex` (409 before done), `/skills` 4-bucket JSON + total, `/pdf` streams `application/pdf` (404 if missing), `/report` parsed JSON.
- `tests/web/test_compile_route.py`: monkeypatch `tectonic.compile_tex` → `(True, <fixture.pdf>, [])` → 200 `application/pdf`; `(False, None, ["l.42 ..."])` → 422 `{ok:false,errors:[...]}`. One `@pytest.mark.integration` real-tectonic test (skip if not installed — mirror `tests/test_compile_smoke.py`).
- `tests/web/test_healthz.py`: `api_key_present` true/false as `OPENROUTER_API_KEY` is set/unset (monkeypatch env).

### GREEN
Implement `routers/jobs.py`, `routers/compile.py`, `app.py`.

## Acceptance
`python3 -m pytest tests/web/ -q` green (unit); `uvicorn src.web.app:create_app --factory` boots and `curl /api/healthz` responds.

## Files
`src/web/routers/{__init__,jobs,compile}.py`, `src/web/app.py`, `requirements.txt` (edit), `tests/web/{test_routes_jobs,test_compile_route,test_healthz}.py`.
