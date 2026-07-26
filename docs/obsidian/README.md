# Obsidian Self-Learning — phase index

Make resume generation self-improving using a local **Obsidian vault as the learning brain**,
while **Postgres stays a write-only journal** (the learning loop never reads it).

## Two loops
- **Loop A — Retrieval (fast, automatic, win-only).** Before a run, pull the bullets from past
  runs that *earned an interview* for a similar role (tag overlap) and inject them into the
  Writer as proven examples. An interview invite is a self-certifying label — no recruiter
  feedback needed.
- **Loop B — Tuning override (slow, human-approved).** `python -m src.vault.propose` drafts
  rubric-weight/threshold proposals from resolved outcomes; the user approves by editing
  `tuning/active.json`; at run time the override is merged onto the **frozen** `config/settings.py`
  defaults, per `jd_type`.

## Core principles
- `config/settings.py` is the **frozen floor** — never written by the program. `active.json` is a
  sparse, user-approved **override** layered on top (the reset point always survives).
- The vault is the only source the learning **reads**; Postgres is only **written**.
- **Per-run toggle** — "Turn off Obsidian learning" on the upload screen skips the feedback
  *inputs* (retrieval + tuning override) and runs the current non-Obsidian flow, but **still writes
  the run note** at the end (`learning_used: false`). Vault stays a complete record either way.
- Outcome is captured by editing the run note's frontmatter in Obsidian
  (`outcome: pending → interview`); silence needs no action (a `pending` note >30 days is never a win).

## Key seam (why no new pipeline node)
`jd_type` is classified at the **start of the worker run** (`runner.run_job`, before
`stream_pipeline`). Tags are therefore known up front, so retrieval examples and the resolved
tuning flow through the **existing** `stream_pipeline(tuning=…, bullet_shapes=…)` override params —
no new LangGraph node, no mid-graph mutation, and `recursion_limit` still computes correctly.

## Vault layout (default `<repo>/vault`, gitignored, env `RESUME_VAULT_DIR`)
```
vault/
├── runs/<date>-<slug>.md   # frontmatter facts + "## Final bullets" + outcome
├── tuning/active.json       # sparse per-tag overrides (user-approved)
├── tuning/proposals.md      # drafts from `propose`; user pastes into active.json
└── dashboard.md             # optional Dataview note
```

## Phases (dependency order)
| # | Phase | Depends on |
|---|-------|-----------|
| 1 | [Vault foundation (config + notes I/O)](phase-1-vault-foundation.md) | — |
| 2 | [Run-note writer](phase-2-run-note-writer.md) | 1 |
| 3 | [JD tagging](phase-3-jd-tagging.md) *(refined by 9)* | — |
| 4 | [Retrieval (Loop A read side)](phase-4-retrieval.md) *(refined by 10)* | 1 |
| 5 | [Writer injection](phase-5-writer-injection.md) | — |
| 6 | [Tuning resolver (Loop B apply side)](phase-6-tuning-resolver.md) | 1 |
| 7 | [Worker wiring + toggle](phase-7-worker-wiring-toggle.md) | 2,3,4,5,6 |
| 8 | [Proposal generator CLI](phase-8-proposal-cli.md) | 1,2 |
| 9 | [Role/Domain tagger split (emitter)](phase-9-role-domain-tagger.md) — refines 3 | — |
| 10 | [Role-gated retrieval (retrieval gate)](phase-10-role-gated-retrieval.md) — refines 4,7 | 9 |

Phase 7 is the integration seam that makes the feature live; 1–6 are independently testable and
inert until 7 wires them. Ship 1→6 in any order, then 7, then 8.

**Follow-up fix (9→10):** phases 9–10 correct a production bad-match bug where an "AI Product Owner"
JD retrieved Backend Engineer bullets on shared tech flavor. Phase 9 splits the flat `jd_type` into an
exclusive `role` + secondary `domains` (emitter); Phase 10 hard-filters retrieval on `role`, then
ranks on `domains` (gate), and rewires the runner + run-note frontmatter. Ship 9 then 10; Loop B's
`resolve_tuning` (Phase 6) is intentionally left untouched — the runner feeds it a flat
`[role, *domains]` list.

## Global acceptance
- `pytest --cov=src` green (≥80%). Vault is a **no-op** when `RESUME_VAULT_DIR` is unset →
  `python -m src.main …` (CLI) behaves byte-identically to today.
- Frontend type-checks with `tsc --noEmit -p tsconfig.app.json` (not bare `npm run lint`).
</content>
