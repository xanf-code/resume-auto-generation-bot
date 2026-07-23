# Phase 6 — Graph, Loop & CLI

**Goal:** Wire every node into the LangGraph state machine, close the revision
loop, and expose a CLI. This is the integration phase — everything lands here.

## Graph (`src/pipeline/graph.py`)

```
parse_resume → analyze_jd → gap_analysis → writer → render → identity_check → compile
                                             ▲                                   │
                    compile fail (≤2 retries)└───────────────────────────────────┘
                                             │
                        compile ok → recruiter_panel (4 concurrent) → aggregator
                                             │                            │
        fail & iteration < 6 (revision_notes)└────────────────────────────┤
                                                        pass / cap hit ────┴──→ emit
```

## Conditional edges

- **`identity_check`**: violation → `writer` (with violation message). Near-
  impossible given the structural design; it's a tripwire.
- **`compile`**: fail → `writer` (with `compile_errors`), bounded by
  `MAX_COMPILE_RETRIES=2` per iteration; does NOT increment the main iteration
  counter. Exhausted → hard-fail with the log.
- **`aggregator`**: `passed` → `emit`; else if `iteration < MAX_ITERATIONS` →
  `writer` (with `revision_notes`, increment `iteration`); else → `emit` best.

## Bookkeeping

- Track `best_score` / `best_latex` every iteration. If the cap is hit without
  passing, emit the best-scoring draft **with a warning**, not the last one.

## Emit node

Writes to `out/`:
- `resume_optimized.pdf`
- `score_report.json` — per-persona breakdowns, aggregate, iteration history.
- **True-gaps section** — competencies the Gap Analyzer flagged `no_evidence`,
  so the user knows what the resume genuinely can't claim.

## CLI (`src/main.py`)

```bash
python -m src.main --resume examples/sample_resume.tex --jd examples/sample_jd.txt --out out/
```
- Validates `ANTHROPIC_API_KEY` at startup.
- Streams per-iteration progress: persona scores, aggregate, pass/fail.

## End-to-end verification

1. `python3 -m pytest tests/` — all unit tests green (aggregator, identity, renderer).
2. Compile smoke test (Phase 3) still passes.
3. Full run on `examples/sample_resume.tex` + `examples/sample_jd.txt` with the
   API key set: loop iterates, scores print, PDF lands in `out/`, score report
   shows panel breakdowns, identity fields in the PDF match the source exactly.
4. Sanity: diff the PDF's companies/titles/dates against the source `.tex` —
   must be identical.

## Exit criteria

- Graph runs start-to-finish, loops on fail, terminates on pass or cap.
- PDF + score report + true-gaps emitted.
- Identity fields provably unchanged end-to-end.
