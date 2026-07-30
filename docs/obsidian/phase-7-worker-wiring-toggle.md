# Phase 7 - Worker wiring + toggle (integration seam)

## Goal
Wire Phases 2–6 into the live run and add the **"Turn off Obsidian learning"** upload checkbox.
This is the only orchestration change and the point where the feature becomes live.

**Prereq:** Phases 2, 3, 4, 5, 6. **Blocks:** —

## Why
Everything before this is inert. Here we classify tags, (optionally) retrieve + resolve tuning,
run through the existing override params, and always write the run note.

## Design
### Contract + toggle (frontend)
- **`frontend/src/components/newjob/NewJobModal.tsx`** — add a **"Turn off Obsidian learning"**
  checkbox near the `enable_scoring` toggle; include `obsidian_learn` in the `createJob(...)` body
  (checked ⇒ `false`; default unchecked ⇒ `true`).
- **`frontend/src/api/types.ts`** — `CreateJobRequest.obsidian_learn?: boolean`.
- **`src/web/schemas.py`** — `JobSubmitRequest.obsidian_learn: bool = True`.

### Threading
- **`src/web/job.py`** — add `jd_type: list[str] | None = None` and `obsidian_learn: bool = True`
  to `Job`.
- **`src/web/job_manager.py`** — map `req.obsidian_learn` onto the `Job` in `submit` (~`job_manager.py:107` path).

### Orchestration — **`src/web/runner.py`** `run_job` (after status=running, ~`runner.py:48`)
```
tags = classify_jd_type(job.jd_raw)          # always (the note needs tags); errors → []
job.jd_type = tags
if job.obsidian_learn:
    examples = retrieve_examples(tags)                     # Phase 4
    tuning, diff = resolve_tuning(tags, job.tuning)        # Phase 6
    log diff to the activity stream                        # visibility (replaces "Proceed?")
else:
    examples, tuning = None, job.tuning                    # current non-Obsidian flow
final_state = stream_pipeline(..., tuning=tuning, bullet_shapes=job.bullet_shapes,
                              proven_examples=examples)
... existing artifact save (Postgres, unchanged) ...
write_run_note(job, final_state, tags)        # ALWAYS (Phase 2); records learning_used=job.obsidian_learn
```
- Every vault/tagging call wrapped so a vault error **never** fails the run.

## Tests (write first) — `tests/web/test_runner_vault.py`, `tests/web/test_schemas.py`, `tests/web/test_job_manager.py`
- `JobSubmitRequest` accepts `obsidian_learn` (default `True`); `submit` maps it onto the `Job`.
- **Integration (learn ON):** seed a temp vault with two `interview` backend notes + an `active.json`
  `by_tag` override; run `run_job` against a backend JD with pipeline LLM nodes monkeypatched (existing
  hermetic pattern). Assert: writer prompt carried the seeded bullets; effective tuning reflects the
  override; a new `runs/*.md` written with `outcome: pending`, `learning_used: true`.
- **Integration (learn OFF):** `obsidian_learn=False` → writer got `proven_examples=None`,
  tuning == `job.tuning`/defaults, **and** a note is still written with `learning_used: false`.
- Vault error path: `write_run_note` raising does not fail the run.

## Acceptance
- `pytest tests/ -q` green (incl. CLI regression; vault is a no-op when `RESUME_VAULT_DIR` unset).
- `tsc --noEmit -p tsconfig.app.json` clean.
- Manual: submit a backend JD → note appears (`pending`); set `outcome: interview`; submit a similar
  JD → activity log shows retrieved examples + tuning diff; submit with the toggle **checked** → no
  retrieval/tuning, but a `learning_used: false` note is still written.

## Files
- `frontend/src/components/newjob/NewJobModal.tsx`, `frontend/src/api/types.ts` (edit)
- `src/web/schemas.py`, `src/web/job.py`, `src/web/job_manager.py`, `src/web/runner.py` (edit)
- `tests/web/test_runner_vault.py` (new); `tests/web/test_schemas.py`, `tests/web/test_job_manager.py` (edit)
</content>
