# Phase 3 — Compiler (non-LLM)

**Goal:** Deterministic rendering + compilation + the mechanical integrity
tripwire. Zero model calls in this phase — build and test it in isolation.

## Template (`src/templates/resume.tex.j2`)

- Single-column, standard fonts, ATS-parseable (no tables/graphics/multicol in
  the experience section).
- Sections: Header (name/contact) → Summary → Skills → Experience → Education.
- **Jinja delimiters remapped** so they don't collide with LaTeX braces:
  `\VAR{ }` for expressions, `\BLOCK{ }` for logic (`variable_start_string` etc.
  set in the Environment).

## Renderer (`src/compiler/renderer.py`)

- Inputs: `identity_ledger` (identity fields ONLY) + `writer_output`
  (bullets/skills/summary ONLY).
- Every injected string is **LaTeX-escaped** (`& % # _ $ { } ~ ^ \`).
- Identity fields are sourced *exclusively* from the ledger — the Writer's output
  never reaches an identity slot in the template. This is integrity guarantee #1.

## Tectonic (`src/compiler/tectonic.py`)

- `subprocess.run(["tectonic", "-X", "compile", tex_path], cwd=tmpdir,
  timeout=60, capture_output=True)`. No shell, no shell-escape.
- On failure: parse the error lines (grep for `error:` / line refs), return them
  as `compile_errors` for the Writer bounce.
- On success: return the PDF path.

## Identity check (`src/compiler/identity_check.py`)

- Assert every `(company, title, start, end)` tuple from the ledger appears
  **verbatim** (post-escape) in the rendered LaTeX.
- Assert **no extra** role headers exist (Writer can't smuggle a fake job in).
- Return `(ok: bool, violations: list[str])`. Any violation → hard abort of the
  draft, bounce to Writer with the violation text. This is integrity guarantee #2.

## Tests (`tests/test_renderer.py`, `tests/test_identity_check.py`)

- Renderer injects locked fields verbatim; special chars escaped.
- Identity check catches: changed date, renamed company, altered title, an
  injected extra role. Each must fail loudly.

## Exit criteria

- Compile smoke test: hand-built `WriterOutput` + ledger → PDF, no LLM.
- All renderer/identity tamper tests pass.
