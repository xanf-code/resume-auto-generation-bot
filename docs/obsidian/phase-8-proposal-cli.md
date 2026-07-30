# Phase 8 - Proposal generator CLI (Loop B draft side)

## Goal
An offline command that reads resolved outcomes and drafts per-tag tuning **proposals** into
`vault/tuning/proposals.md`, each with a ready-to-paste `active.json` snippet. It **never** writes
`active.json` — the human approves by pasting.

**Prereq:** Phases 1, 2. **Blocks:** —

## Why
This closes Loop B without auto-applying anything: outcomes → suggestion → human approval → override.
Runs occasionally (only when new outcomes have landed), not per run.

## Design
**`src/vault/propose.py`** — `python -m src.vault.propose [--tag <t>] [--min-sample N]`:
- `load_all_runs` (Phase 1); resolve each note's outcome (pending >30d → no-response).
- Group by tag; per tag split into **wins** (`interview`/`offer`) vs **non-wins**
  (`rejected*`/`no_response`).
- **Min-sample gate:** only propose for a tag with ≥3 wins **and** ≥3 non-wins (default; `--min-sample`);
  otherwise emit "insufficient data".
- **Heuristic (deterministic):** for each rubric dimension, compute mean of `score_report` sub-scores
  for wins vs non-wins. If a dimension is materially higher among wins, propose nudging its weight up,
  offset from the weakest-signal dimension, keeping the five weights summing to 1.0. Optionally
  propose `threshold` just below the min winning aggregate.
- **Output:** append to `tuning/proposals.md` a dated, human-readable rationale **plus** a fenced
  JSON snippet the user can paste into `active.json` `by_tag`. Idempotent per (date, tag).

## Tests (write first) — `tests/vault/test_propose.py`
- Grouping by tag; win/non-win split; 30-day pending→no-response applied.
- Min-sample gate: <3/<3 → "insufficient data", no proposal.
- Heuristic direction: synthetic notes where wins score higher on `keyword_match` → proposal raises
  `keyword_match`; snippet weights sum to 1.0.
- **Never** writes `active.json` (only `proposals.md`).
- Disabled vault → clean exit, nothing written.

## Acceptance
- `pytest tests/vault/test_propose.py -q` green.
- `python -m src.vault.propose` on a seeded vault produces a paste-ready snippet; pasting it into
  `active.json` changes the next run's effective tuning (via Phase 6).

## Files
- `src/vault/propose.py` (new), `tests/vault/test_propose.py` (new)
</content>
