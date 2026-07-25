# Phase 8 — Web Core: Config, DTOs, Job Model, Event Translation

**Goal:** Stand up the pure (no threading, no HTTP) foundation of `src/web/`: settings, API DTOs, the in-memory job model, and the translation from a pipeline stream-delta to a client `ProgressEvent`.

**Prereq:** Phase 7. **Blocks:** Phases 9-10.

## Modules (each <500 lines)
- `src/web/__init__.py`
- `src/web/config.py` — `WebSettings` read from env: `MAX_CONCURRENT_JOBS=3`, `OUT_ROOT="out"`, `EVENT_BUFFER_MAX=500`, `HOST`, `PORT`.
- `src/web/schemas.py` — Pydantic DTOs at the API boundary (separate from pipeline schemas): `JobSubmitRequest` (label, resume_tex, jd_text, enable_scoring=False; validators reject empty tex/jd), `JobSummary`, `JobDetail` (+ nested `artifacts` URLs), `ProgressEvent`, `CompileRequest`, `CompileErrorResponse`, `SkillDumpDTO`.
- `src/web/job.py` — `JobStatus(str, Enum)` = queued/running/done/failed; `Job` dataclass (id, label, status, timestamps, out_dir, jd_name, live snapshot fields, `events: EventBuffer`, `subscribers: set`, inputs, terminal artifacts); `EventBuffer` = bounded `deque(maxlen=EVENT_BUFFER_MAX)` + monotonic `seq`, with `append(event)` and `since(seq)`.
- `src/web/events.py` — `STAGE_LABELS: dict[str,str]`, `STAGE_ORDER`, `pct_estimate(stage, iteration)`, `build_progress_event(job_id, flat_delta, state) -> ProgressEvent | None`. Imports `_KEY_TO_NODE` from `src.main`.

## Event contract
```json
{ "seq":42, "job_id":"...", "type":"progress",
  "stage":"recruiter_panel", "human_label":"Scoring against recruiter panel",
  "iteration":2, "aggregate_score":74.5, "passed":false,
  "persona_scores":[{"persona":"ATS Matcher","keyword_match":80,"impact_quality":70,
                     "coherence":75,"plausibility":68,"formatting":72,"notes":"..."}],
  "pct_estimate":62, "ts":"..." }
```
- Stage via `next((v for k,v in _KEY_TO_NODE.items() if k in flat), None)`; return `None` (skip) if no known key.
- `persona_scores` only when `panel_scores in flat`; serialize each `PanelScore.model_dump()`.
- `pct_estimate`: extraction spine (parse→skills) 0-25%; writer↔compile↔panel loop 25-90% scaled by `iteration/MAX_ITERATIONS`; emit/score_report 90-100%. Clamp so it never decreases within a job.

## TDD

### RED
- `tests/web/test_events.py`: each `_KEY_TO_NODE` key → expected `stage` + `human_label`; delta with no known key → `None`; `persona_scores` present only with `panel_scores` (all 5 dims + notes serialized); `pct_estimate` monotonic-non-decreasing across scripted deltas `parse→...→writer(it1)→compile→writer(it2)` (no regression on the writer back-edge).
- `tests/web/test_job_buffer.py`: `append` assigns increasing `seq`; `since(seq)` returns only newer; after `maxlen` eviction `since` still returns the tail correctly.
- `tests/web/test_schemas.py`: `JobSubmitRequest` rejects empty/whitespace `resume_tex` or `jd_text` (ValidationError); label is trimmed; `SkillDumpDTO.total` = sum of 4 lists.

### GREEN
Implement the four modules to pass.

## Acceptance
`python3 -m pytest tests/web/test_events.py tests/web/test_job_buffer.py tests/web/test_schemas.py -q` passes; files each <500 lines.

## Files
`src/web/{__init__,config,schemas,job,events}.py`, `tests/web/{test_events,test_job_buffer,test_schemas}.py`.
