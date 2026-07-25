# Phase 1 - Per-application tuning (backend)

## Goal
Let each application (job) run the pipeline with a caller-chosen set of tuning
knobs instead of the fixed module constants in `config/settings.py`. Absent a
config, behaviour is byte-identical to today (defaults sourced from the same
constants).

## Exposed knobs (from `config/settings.py`)
| Field | Default | Range | Meaning |
|-------|---------|-------|---------|
| `threshold` | 78 | 0–100 | Aggregate score a draft must clear to PASS. |
| `plausibility_floor` | 20 | 0–100 | Min Skeptic plausibility; vetoes an otherwise-passing draft (fabrication guard). |
| `max_iterations` | 4 | 1–8 | Writer↔score revision loop budget. |
| `max_compile_retries` | 2 | 0–5 | Per-iteration LaTeX compile bounce budget. |
| `max_identity_retries` | 2 | 0–5 | Global identity-violation retry budget. |
| `max_length_retries` | 3 | 0–6 | Per-iteration bullet-length retry budget. |
| `rubric_weights` | km .30 / iq .20 / coh .20 / plaus .15 / fmt .15 | each 0–1, **sum normalized to 1.0** | Weights collapsing a persona's 5 dims to a composite. |

## Design
1. **`src/pipeline/tuning.py`** - `PipelineTuning` (frozen dataclass) with the 7
   fields above; `RUBRIC_KEYS` tuple; `PipelineTuning.defaults()` reads the
   current `config.settings` constants (single source of truth); `get_tuning(state)`
   returns `state.get("tuning") or PipelineTuning.defaults()`.
2. **`PipelineState`** gains a `tuning: PipelineTuning` channel.
3. **`aggregator.py`** - `persona_composite` / `aggregate` / `decide` gain
   optional `weights` / `threshold` / `floor` params (default to today's
   constants → existing tests unchanged). The `aggregator` node reads
   `get_tuning(state)` and passes them through.
4. **`graph.py`** - the four route fns + `bookkeep_node` read
   `get_tuning(state).max_*` instead of module constants (fallback = defaults →
   existing graph tests unchanged).
5. **`events.py`** - `pct_estimate(stage, iteration, max_iterations)`; the
   default keeps current behaviour, `build_progress_event` passes the job's value
   from `state["tuning"]`.
6. **Web boundary** - `TuningDTO` + `RubricWeightsDTO` in `web/schemas.py` with
   `Field(ge=…, le=…)` range clamps and a validator that **normalizes weights to
   sum 1.0** (rejects all-zero). `JobSubmitRequest.tuning: TuningDTO | None = None`.
   `TuningDTO.to_tuning() -> PipelineTuning`.
7. **Threading** - `Job.tuning`; `JobManager.submit` maps `req.tuning.to_tuning()`;
   `run_job` passes `tuning=job.tuning`; `stream_pipeline(..., tuning=None)` seeds
   `initial_state["tuning"]` and scales `recursion_limit` off `max_iterations`.

## Tests (write first)
- `tests/test_tuning.py`: defaults match settings; `get_tuning` fallback; frozen.
- `tests/web/test_schemas.py`: range clamp/reject; weight normalization to 1.0;
  `JobSubmitRequest` tuning optional → None.
- `tests/test_aggregator.py`: `decide`/`aggregate` honour custom threshold/weights;
  node reads state tuning.
- `tests/test_graph.py`: `route_after_aggregator` honours `max_iterations` from state.
- `tests/web/test_job_manager.py`: `submit` maps tuning onto the Job.
- `tests/web/test_events.py`: `pct_estimate` honours `max_iterations`.
</content>
