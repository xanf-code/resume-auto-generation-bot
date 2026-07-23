# Phase 1 — State & Schemas

**Goal:** The typed backbone. Everything downstream reads/writes `PipelineState`
and speaks in Pydantic models that double as `messages.parse()` schemas.

## `src/pipeline/state.py`

`PipelineState(TypedDict)` — fields grouped by lifecycle stage:

- **inputs:** `resume_tex_raw`, `jd_raw`
- **extraction:** `resume_struct`, `identity_ledger`, `jd_vector`, `gap_targets`
- **writer:** `writer_output`, `latex_rendered`
- **compile:** `compile_ok`, `compile_errors`
- **eval:** `panel_scores`, `aggregate_score`, `passed`, `revision_notes`
- **bookkeeping:** `iteration`, `best_score`, `best_latex`, `pdf_path`

## Pydantic models (same file or `schemas.py`)

- `IdentityLedger` — frozen list of `Role(company, title, start, end)` +
  `name`, `contact`. This is the immutable source of truth.
- `ResumeStruct` — roles (each with ledger identity + `source_evidence: list[str]`
  of original bullets), `education`, `skills`.
- `JDVector` — `weighted_skills: list[SkillWeight]` (name + 0–1 weight),
  `ats_keywords: list[str]` (literal match strings), `seniority`,
  `must_mirror: list[str]` (top-5 phrases).
- `ReframingTarget` — `competency`, `weight`, `host_role_index`,
  `real_evidence: list[str]`, `framing_guidance: str`, `no_evidence: bool`.
- `WriterOutput` — `roles: list[RoleBullets]` (index + `bullets: list[str]` ONLY),
  `skills: list[str]`, `summary: str`. **No identity fields exist in this schema.**
- `PanelScore` — `persona`, `keyword_match`, `impact_quality`, `coherence`,
  `plausibility`, `formatting` (all int 0–100), `notes: str`.

> Structured-output constraint: schemas must use `additionalProperties: false`
> and avoid min/max numeric bounds (validate ranges in code). The SDK strips
> unsupported constraints, but keep schemas flat and enum-driven.

## `src/pipeline/llm.py`

- `client()` → cached `anthropic.Anthropic()` (env key).
- `parse_fast(system, user, schema)` → `client.messages.parse(model=MODEL_FAST, ...)`
  returning `schema` instance.
- `parse_strong(system, user, schema, effort="high")` → same on `MODEL_STRONG`
  with `thinking={"type":"adaptive"}`, `output_config={"effort": effort}`.
  **No `temperature`/`top_p`** — rejected on Opus 4.8.
- `max_tokens` default 16000 (non-streaming); higher agents stream if needed.

## Exit criteria

- All models import and instantiate.
- A round-trip test: build a fake `IdentityLedger`, serialize/validate — passes.
- `llm.py` helpers importable (no live call needed yet).
