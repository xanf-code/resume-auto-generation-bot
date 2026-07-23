# Phase 2 — Extraction Agents (Haiku)

**Goal:** Turn raw inputs into structured artifacts. Three cheap, fast agents.
These lock the identity ledger and build the requirement vector the Writer
optimizes against.

## Parser (`src/agents/parser.py` + `prompts/extraction.py`)

- Input: `resume_tex_raw`. Output: `ResumeStruct` (+ derived `IdentityLedger`).
- **Hard rules:** copy company / title / dates **character-exact** into the
  ledger — never paraphrase, reformat, or "clean up" identity fields.
- Capture each role's existing bullets as `source_evidence` (this is the ground
  truth the Writer and Skeptic trace against).
- Node writes `resume_struct` + `identity_ledger` to state.

## JD Analyzer (`src/agents/jd_analyzer.py`)

- Input: `jd_raw`. Output: `JDVector`.
- Rank required skills with 0–1 weights. Extract **literal ATS keyword strings**
  (what an ATS substring-matches, e.g. "REST APIs", "ETL pipelines", "Salesforce").
- Identify seniority signals and the top-5 "must mirror" phrases.

## Gap Analyzer (`src/agents/gap_analyzer.py`)

- Inputs: `resume_struct`, `jd_vector`. Output: `list[ReframingTarget]`.
- For each JD competency the resume underrepresents:
  - Pick the best **host role** to reframe under.
  - Cite the **specific real bullets** that are genuine adjacent evidence.
  - Write `framing_guidance`: how to describe that real work in JD vocabulary.
- **Hard rule:** if there is *no* genuine adjacent evidence, set
  `no_evidence: true` and exclude it from reframing. Real gaps get reported to
  the user at the end, not papered over.

## Example: the Salesforce case (from the spec)

Resume has ETL / data-integration work; JD emphasizes Salesforce.
- ✅ `framing_guidance`: "Frame the CRM-sync ETL job as building REST-based data
  integrations that syncing customer records into a CRM platform — surfaces
  Salesforce-*adjacent* competency (API integration, data mapping, CRM data models)."
- ❌ Never: "administered Salesforce" (that tool isn't in the source resume).
- If the resume has zero CRM/integration evidence → `no_evidence: true`.

## Exit criteria

- Each agent returns its schema on the sample resume/JD.
- Ledger fields are byte-identical to the source `.tex`.
- Gap targets cite real bullet text, and a deliberately-absent competency gets
  `no_evidence: true`.
