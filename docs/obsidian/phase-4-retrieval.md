# Phase 4 - Retrieval (Loop A read side)

> **Superseded/refined by [Phase 10 — Role-gated retrieval](phase-10-role-gated-retrieval.md).** The
> "any tag overlap" match below is replaced by a hard `role` equality filter, then domain-Jaccard
> ranking. Read Phase 10 for the current `retrieve_examples` signature and legacy-note handling.

## Goal
Given the current run's tags, return a prompt-ready block of bullets from past runs that **earned an
interview** for a **similar role**. Returns `None` when nothing qualifies (cold start).

**Prereq:** Phase 1. **Blocks:** Phase 7.

## Why
This is the high-value loop: reuse what actually worked. It needs only the outcome label — no
recruiter feedback, no explanation of *why*.

## Design
**`src/vault/retrieval.py`** — `retrieve_examples(tags, *, settings, k=3) -> str | None`:
- `load_all_runs` (Phase 1). Keep notes where `outcome ∈ {interview, offer}` **and** `jd_type`
  overlaps `tags`.
- Resolve outcome at read time: a `pending` note whose `created` is >30 days old counts as
  no-response → excluded.
- Rank by (tag-overlap count, then `internal_score`) desc; take top `k`.
- Format each note's `## Final bullets` into a labelled block:
  `## PROVEN EXAMPLES (bullets that earned interviews for similar roles — match framing/emphasis,
  do not invent facts)` followed by the bullets.
- No matches / disabled vault → `None` (writer then behaves exactly as today).

## Tests (write first) — `tests/vault/test_retrieval.py`
- Win-only filter: `rejected`/`no_response`/`pending` excluded; `interview`/`offer` included.
- Tag overlap required; non-overlapping tags excluded.
- 30-day `pending` → excluded.
- Ranking: higher overlap then higher `internal_score` first; respects `k`.
- Cold start (no wins) and disabled vault → `None`.

## Acceptance
- `pytest tests/vault/test_retrieval.py -q` green.
- Output string is drop-in for the Writer's `proven_examples` slot (Phase 5).

## Files
- `src/vault/retrieval.py` (new), `tests/vault/test_retrieval.py` (new)
</content>
