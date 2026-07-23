# Resume-Bot — Phased Build Docs

Agentic resume-optimization pipeline. Tailors a LaTeX resume to a target job
description via a Writer → Recruiter-Panel → Aggregator revision loop, then
compiles an ATS-optimized PDF. Identity fields (companies, titles, dates) are
immutable and enforced three ways.

## Phase Index

| Phase | File | Goal | Depends on |
|-------|------|------|-----------|
| 0 | [phase-0-setup.md](phase-0-setup.md) | Toolchain, deps, project skeleton | — |
| 1 | [phase-1-state-and-schemas.md](phase-1-state-and-schemas.md) | `PipelineState` + Pydantic models + LLM helpers | 0 |
| 2 | [phase-2-extraction-agents.md](phase-2-extraction-agents.md) | Parser / JD Analyzer / Gap Analyzer (Haiku) | 1 |
| 3 | [phase-3-compiler.md](phase-3-compiler.md) | Renderer, tectonic, identity check, template | 1 |
| 4 | [phase-4-writer.md](phase-4-writer.md) | Writer agent (Opus) + hard rules | 2, 3 |
| 5 | [phase-5-recruiter-panel-aggregator.md](phase-5-recruiter-panel-aggregator.md) | 4 personas + weighted scoring + revision notes | 4 |
| 6 | [phase-6-graph-and-cli.md](phase-6-graph-and-cli.md) | LangGraph wiring, loop, CLI, e2e | 2,3,4,5 |

## Integrity model (the spine of the whole thing)

1. **Structural** — Writer's output schema has no identity fields. It emits
   bullets/skills/summary only; the renderer injects locked companies/titles/dates
   from the Parser's ledger. The Writer *cannot* touch them.
2. **Mechanical** — `identity_check.py` diffs rendered LaTeX against the ledger.
   Any drift aborts the draft.
3. **Prompt + panel** — reframing = describing *real* work in the JD's vocabulary,
   never claiming un-sourced tools. The Skeptic persona scores traceability;
   plausibility is the highest-weighted rubric dimension.

## Stack

- LangGraph (`StateGraph` over `PipelineState` TypedDict)
- Anthropic SDK direct (`messages.parse()` + Pydantic for structured output)
- `claude-opus-4-8` (Writer + Recruiters), `claude-haiku-4-5` (extraction)
- Jinja2 LaTeX template + tectonic subprocess compile

## Global config

`THRESHOLD=88`, `MAX_ITERATIONS=6`, `MAX_COMPILE_RETRIES=2`,
`PLAUSIBILITY_FLOOR=70`. Rubric weights: plausibility 0.30, keyword_match 0.20,
impact_quality 0.20, coherence 0.15, formatting 0.15.
