# Phase 5 - Writer injection

## Goal
Let a run carry an optional `proven_examples` string that the Writer sees as a new prompt section.
Byte-identical to today when `None`.

**Prereq:** none (pairs with Phase 4 at runtime). **Blocks:** Phase 7.

## Why
The retrieved examples must reach the Writer. This reuses the **exact** per-run override pattern that
`bullet_shapes` already uses — `initial_state` + `state.get(...)` in the pure prompt builder — so no
new pipeline node and no graph change.

## Design
1. **`src/main.py`** `stream_pipeline` — add `proven_examples: str | None = None`; seed
   `initial_state["proven_examples"]` **only when not None** (mirror the `bullet_shapes` block at
   `main.py:179-180`). Because every revision back-edge re-enters at `writer`, the value persists
   across the loop for free.
2. **`src/agents/writer.py`** `build_writer_user_message` — after the REFRAMING TARGETS section
   (`writer.py:155-156`), append a `## PROVEN EXAMPLES …` block from `state.get("proven_examples")`.
   Omit the section entirely when absent. Pure/deterministic — no API call.

## Tests (write first) — `tests/test_writer_prompt.py`, `tests/test_stream_pipeline.py`
- `build_writer_user_message` includes the PROVEN EXAMPLES block (with the exact content) when
  `proven_examples` is set; **omits** it when `None` (assert the header string is absent).
- Section ordering: appears after REFRAMING TARGETS, before REVISION/COMPILE sections.
- `stream_pipeline` seeds `initial_state["proven_examples"]` when passed and omits the key when
  `None` (existing stream-pipeline stubbing pattern).

## Acceptance
- `pytest tests/test_writer_prompt.py tests/test_stream_pipeline.py -q` green.
- Existing writer/prompt tests remain green (no change when `proven_examples is None`).

## Files
- `src/main.py`, `src/agents/writer.py` (edit)
- `tests/test_writer_prompt.py`, `tests/test_stream_pipeline.py` (edit/new)
</content>
