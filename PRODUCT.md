# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Single power user: the owner of this repository, preparing job applications for themselves. Operates in a focused, deliberate mode — loading a master LaTeX resume, pasting a target job description, and running the full pipeline to produce a submission-ready PDF with a quantified score.

## Product Purpose

Résumé Desk optimizes a LaTeX resume against a specific job description through an autonomous multi-agent pipeline. It rewrites the resume, enforces that no credentials are fabricated, compiles a production-quality PDF via Tectonic, and produces a structured score report with recruiter-persona breakdowns. Success means walking away with a tailored PDF confident enough to submit.

## Positioning

Three mechanisms combined that a single ChatGPT prompt cannot replicate:

1. **Multi-agent recruiter panel** — four independent AI personas (ATS Matcher, Hiring Manager, Technical Screener, Skeptic) each score the resume separately; an aggregator synthesizes the result. No single-pass judgment.
2. **Identity ledger** — a constraint system that tracks the original resume's factual claims and rejects any rewrite that invents credentials, inflates titles, or fabricates outcomes. Rewrites stay grounded.
3. **LaTeX → PDF compile pipeline** — output is a Tectonic-compiled PDF, not rich text or DOCX. The visual artifact is indistinguishable from a manually typeset resume.

## Operating Context

- Source material: a master `.tex` resume file and one or more `.txt` job descriptions
- Iteration loop: submit → score → rewrite → re-score until aggregate score is acceptable
- Output bundle per JD: `resume.pdf`, `score_report.json`, `skills.mdx`
- Backend: Python + LangGraph + OpenRouter API; frontend: React + Vite served by FastAPI in production
- Development is local; no public deployment or multi-user auth is planned

## Capabilities and Constraints

- Accepts LaTeX source only (not DOCX or plain text resumes)
- Requires an `OPENROUTER_API_KEY` environment variable; fails fast if absent
- Compile requires Tectonic installed locally
- Max pipeline iterations configurable via `MAX_ITERATIONS` in `config/settings`
- Score report includes per-persona breakdowns and a final aggregate
- Skills output available as structured JSON or `.mdx`

## Brand Commitments

- **Name:** Résumé Desk
- **Design system:** "Manuscript" — editorial print aesthetic. Warm paper (`#f7f3ec`), ink black (`#1c1b19`), one disciplined accent (editorial vermilion `#c0362c`). Fraunces serif for display headings, Inter for UI chrome, JetBrains Mono only inside the LaTeX editor. No dark terminal aesthetics. No neon colors. No gradients. Print-flat (no drop shadows). This is locked and the owner has strong feelings about it.
- **Tone:** precise, tool-forward, no marketing copy. The interface recedes behind the work.

## Evidence on Hand

- `examples/main.tex` — real master resume (owner's)
- `examples/vestwell_resume.txt` — plain-text resume variant
- `out/` — compiled PDF and score report outputs from prior runs
- No testimonials, benchmarks, or external case studies; do not fabricate any

## Product Principles

1. **The artifact is the product.** A tailored, compiled PDF is the only deliverable that matters; the UI exists to produce it, not to be experienced for its own sake.
2. **Honesty is the constraint, not a feature.** The identity ledger is non-negotiable — a rewrite that invents credentials is worse than no rewrite.
3. **Depth over breadth.** One user, one workflow, done with precision. No feature dilution for a hypothetical broader audience.
4. **Editorial craft signals intent.** The Manuscript design system is not decoration; it signals that this tool treats resumes as documents, not data blobs.
5. **Fail fast, iterate honestly.** The pipeline surfaces gaps and scores rather than flattering the user; the point is to know where you stand before submitting.
