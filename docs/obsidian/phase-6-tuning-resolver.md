# Phase 6 - Tuning resolver (Loop B apply side)

## Goal
Turn `vault/tuning/active.json` into a `PipelineTuning` for the current run by merging its sparse
per-tag overrides onto the frozen `config/settings.py` defaults. `settings.py` is never written.

**Prereq:** Phase 1. **Blocks:** Phase 7.

## Why
This is how approved learning reaches a run without mutating the baseline. The default stays the
reset point; `active.json` is a deletable, diffable override.

## Design
**`src/vault/tuning.py`** — `resolve_tuning(tags, base, *, settings) -> tuple[PipelineTuning, dict]`:
- **Base/precedence:** `base = job.tuning` when the user set knobs in the UI this run, else
  `PipelineTuning.defaults()`. Explicit UI tuning **wins** over the vault override.
- Read `active.json` `by_tag`; keys are `+`-joined sorted tag combos. A key **matches** iff its tags
  ⊆ run `tags`; if several match, the **most specific** (most tags) wins.
- Merge that entry's fields onto `base`; **renormalize `rubric_weights` to sum 1.0**; build a new
  frozen `PipelineTuning`.
- Return the tuning **and a diff dict** (changed field → old→new) for the activity log — this is the
  visibility that replaces the CLI "Proceed?" gate.
- Disabled vault / no match / malformed json → return `(base, {})` (safe fallback).

## Tests (write first) — `tests/vault/test_tuning_resolver.py`
- Merge applies overrides; unlisted fields fall back to defaults.
- Most-specific match wins among multiple `by_tag` keys; non-subset keys ignored.
- Weights renormalize to 1.0 after a partial override.
- Precedence: explicit `job.tuning` beats vault override.
- Disabled / no-match / malformed `active.json` → `(base, {})`, no raise.

## Acceptance
- `pytest tests/vault/test_tuning_resolver.py -q` green.
- Returned `PipelineTuning` is frozen and usable directly as `stream_pipeline(tuning=…)`.

## Files
- `src/vault/tuning.py` (new), `tests/vault/test_tuning_resolver.py` (new)
</content>
