# Phase 12 — Integration & Prod Serving

**Goal:** Wire the frontend and backend into one runnable app, confirm SSE works through the dev proxy, serve the built SPA from FastAPI in prod, and run the end-to-end smoke.

**Prereq:** Phases 7–11.

## Dev proxy
`frontend/vite.config.ts`: `server.proxy` maps `/api` → `http://localhost:8000` with `changeOrigin: true`. Verify SSE passes through un-buffered (backend already sets `X-Accel-Buffering: no`; keep the `text/event-stream` content type). All frontend calls use base `/api` → no CORS in dev.

## Prod serving (single origin)
In `src/web/app.py`, **after** all `/api` routes, mount:
```python
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="spa")
```
with an SPA fallback so unknown non-`/api` paths return `index.html`. One origin → no CORS, cookies/SSE "just work", one process to deploy. Build with `cd frontend && npm run build`.

## pdf.js worker
Confirm the `pdfjs-dist` worker loads under Vite (import worker via `?url` and set `GlobalWorkerOptions.workerSrc`). Common footgun — verify once in a real browser.

## TDD / tests
- Add one `@pytest.mark.integration` test exercising the real `tectonic.compile_tex` (skip if tectonic not on PATH — mirror `tests/test_compile_smoke.py`).
- Keep the full suite green: `python3 -m pytest tests/ -q`.

## End-to-end manual verification
1. `uvicorn src.web.app:create_app --factory` (:8000) + `cd frontend && npm run dev` (:5173).
2. Submit `examples/main.tex` + `examples/vestwell_resume.txt` with a label.
3. Live loader advances through stages + iterations + 4 persona scores; on finish → browser notification + toast + sound.
4. Open the done job → editor seeded with `best_latex`, skills sidebar populated, PDF pane shows the pipeline PDF.
5. Edit a bullet → Compile → PDF swaps to "my compile" → Download saves the PDF.
6. Submit 2–3 jobs at once → rail tracks all concurrently; a 4th queues (cap = 3); each fires its own completion alert.

## Acceptance
All of the above pass; `npm run build` produces `frontend/dist` and the app is fully usable served from FastAPI alone.

## Files
`frontend/vite.config.ts` (edit), `src/web/app.py` (edit — static mount), one integration test.
