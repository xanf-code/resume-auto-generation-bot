# Phase 5 — Recruiter Panel & Aggregator

**Goal:** Score the draft from four adversarial lenses, aggregate with
plausibility weighted highest, and either pass or distill concrete revision
instructions. This is the quality gate and the truthfulness guard.

## Recruiter Panel (`src/agents/recruiters.py` + `prompts/recruiters.py`)

Four Opus personas, **run concurrently**, each returns a `PanelScore` via
`parse_strong(..., PanelScore)`. Shared rubric, distinct lens:

| Persona | Lens | Sees |
|---------|------|------|
| **ATS Matcher** | Keyword coverage vs `jd_vector`; machine-readability | rendered LaTeX, jd_vector |
| **Hiring Manager** | Impact, outcomes, seniority fit, narrative | rendered LaTeX, jd_vector |
| **Technical Screener** | Technical coherence; would this survive a phone screen | rendered LaTeX, jd_vector |
| **Skeptic** | Adversarial traceability; flags overstatement & un-sourced tools | rendered LaTeX, jd_vector, **`resume_struct`** |

- Rubric dimensions (each 0-100): `keyword_match`, `impact_quality`, `coherence`,
  `plausibility`, `formatting` + free-text `notes` (specific, actionable).
- **Skeptic is prompted to refute, not confirm** — for each bullet it checks
  traceability to `source_evidence` and defaults to a low plausibility score when
  a claim overstates or names an un-sourced tool.
- Concurrency: `asyncio.gather` over the four calls (or LangGraph fan-out
  branches merging into the aggregator).

## Aggregator (`src/agents/aggregator.py`)

Pure-code scoring + one Opus call only when failing:

1. **Per-persona composite** = weighted mean using `RUBRIC_WEIGHTS`
   (plausibility **0.30**, keyword_match 0.20, impact_quality 0.20,
   coherence 0.15, formatting 0.15).
2. `aggregate_score` = mean of the four persona composites.
3. **Plausibility floor:** if the Skeptic's `plausibility < 70` →
   automatic fail regardless of aggregate. Fabrication guard.
4. **Pass ⇔** `aggregate_score ≥ 88` **and** floor holds.
5. On fail: one Opus call distills all persona `notes` into ranked, concrete,
   deduplicated `revision_notes` (max ~10 directives), prioritized by weighted
   rubric impact. Feed to Writer.

## Tests (`tests/test_aggregator.py`)

- Weighted-mean math correct.
- Plausibility floor forces a fail even when aggregate ≥ 88.
- Pass only when both conditions hold.
- Note distillation is deterministic in structure (mock the LLM call).

## Exit criteria

- Panel returns four scores concurrently on a rendered sample.
- Aggregator math + floor tests pass.
- A low-plausibility draft is rejected even with a high aggregate.
