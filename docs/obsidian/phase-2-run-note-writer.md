# Phase 2 - Run-note writer

## Goal
At the end of every run, write one `runs/<date>-<slug>.md` note capturing the facts the learning
loop needs and the bullets it will reuse. No-op when the vault is disabled.

**Prereq:** Phase 1. **Blocks:** Phase 7, 8.

## Why
The note is the unit of memory: frontmatter = machine-readable facts; `## Final bullets` = the
retrieval corpus; `outcome` = the field the user edits in Obsidian later.

## Design
**`src/vault/writer.py`** — `write_run_note(job, final_state, tags, *, settings) -> Path | None`:
- **Frontmatter:** `job_id`, `label`, `jd_name`, `jd_type` (tags), `created` (ISO),
  `internal_score` (`aggregate_score`), `passed`, `threshold_used`, `rubric_weights_used`,
  `bullet_shapes_used`, `learning_used` (from the toggle), `outcome: pending`, `outcome_date:` (empty).
- **Body:** `## Final bullets` from `final_state["writer_output"].roles[].bullets`
  (fallback: parse from `best_latex`); `## Score breakdown` from `score_report`
  (aggregate + per-persona + lowest persona).
- **Idempotent by `job_id`:** re-writing the same job overwrites its note; **never** clobbers an
  existing note's `outcome`/`outcome_date` if present (preserve user edits on re-run).
- Slug = `<created-date>-<slugified label>`. Disabled vault → return `None`, write nothing.

## Tests (write first) — `tests/vault/test_writer.py`
- Frontmatter has all fields with correct types; `outcome: pending`, `learning_used` reflects arg.
- `## Final bullets` contains each writer bullet verbatim.
- Re-writing preserves an already-set `outcome: interview` / `outcome_date`.
- Disabled vault → returns `None`, no file created.
- Slug is filesystem-safe and stable for the same job.

## Acceptance
- `pytest tests/vault/test_writer.py -q` green.
- A note round-trips through Phase 1 `read_note`.

## Files
- `src/vault/writer.py` (new), `tests/vault/test_writer.py` (new)
</content>
