# Phase 4 — Writer Agent (Opus)

**Goal:** The optimizer. Emits bullets/skills/summary that mirror the JD while
staying provably truthful. Depends on Phase 2 (artifacts) and Phase 3 (it
consumes compile errors on bounce).

## `src/agents/writer.py` + `prompts/writer.py`

**Inputs:** `resume_struct`, `jd_vector`, `gap_targets`, and on iterations ≥ 2:
prior `writer_output` + `revision_notes`; on a compile bounce: `compile_errors`.

**Output:** `WriterOutput` (bullets + skills + summary — **no identity fields**;
they're not even in the schema).

## Hard rules block (verbatim intent)

1. **Never output company names, titles, or dates.** (Also structurally excluded.)
2. **Every bullet must trace to real experience** in `resume_struct.source_evidence`.
   Mirror JD keyword phrasing from `jd_vector` — but only where truthful.
3. **Name a tool/technology only if it appears in the source resume.** Adjacency
   is expressed through the *work*, not by claiming the tool:
   - ✅ "Integrated CRM data via REST APIs, mapping customer records across systems"
   - ❌ "Administered Salesforce" — unless Salesforce is literally in the source.
4. **Never invent metrics.** Quantify only where the source provides numbers.
5. Strong action verbs, 1-2 lines per bullet, ATS-safe glyphs only.
6. Apply each `ReframingTarget.framing_guidance` to its `host_role_index`, drawing
   strictly from that target's `real_evidence`.

## Revision behavior

- On `revision_notes` present: treat them as a ranked directive list; address the
  highest-weighted items first, preserve bullets that already scored well.
- On `compile_errors` present: fix the LaTeX-affecting content (bad glyph, overlong
  bullet) — this is a compile retry, not a full revision iteration.

## Model config

`parse_strong(system, user, WriterOutput, effort="high")` —
`claude-opus-4-8`, adaptive thinking, no sampling params.

## Exit criteria

- On the sample inputs, produces a valid `WriterOutput`.
- Manual spot-check: no un-sourced tool names; reframed bullets trace to real
  evidence; identity fields absent from output.
- Feeding fake `revision_notes` visibly changes the next draft.
