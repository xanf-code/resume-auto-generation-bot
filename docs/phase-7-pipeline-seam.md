# Phase 7 — Pipeline Seam Refactor

**Goal:** Expose the LangGraph pipeline to a web layer via raw string inputs + a per-node progress callback, without duplicating graph logic. This is the **only** edit to core pipeline code.

**Prereq:** none. **Blocks:** Phases 8–12.

## Why
The web layer must (a) accept resume/JD as in-memory strings (no file paths), and (b) observe each node as it completes to stream live progress. Today `src/main.py:run()` bundles file I/O + the `graph.stream` loop + stdout printing into one function. We split the observable core out and keep `run()` as a thin CLI wrapper so CLI behavior and existing tests are unchanged.

## Design
New function in `src/main.py`:

```python
def stream_pipeline(
    resume_tex_raw: str,
    jd_raw: str,
    out_dir: str,
    jd_name: str,
    enable_scoring: bool = False,
    resume_struct: ResumeStruct | None = None,
    identity_ledger: IdentityLedger | None = None,
    on_step: Callable[[dict, dict], None] | None = None,
) -> dict:
    """Build the graph, run graph.stream, accumulate final_state, and invoke
    on_step(flat_delta, accumulated_state) once per streamed node. No file
    reads, no stdout printing. Calls require_api_key() first (fail-fast)."""
```

- Body = current `run()` lines 140-168 + 182-183 (initial-state build + stream loop), with `on_step(flat, final_state)` called after `final_state.update(flat)`.
- `run()` becomes: `require_api_key()` → `_read_text` both files → `stream_pipeline(..., jd_name=Path(jd_path).stem, on_step=_stdout_adapter)` → `_print_summary`. `_stdout_adapter` reproduces the current per-node log + `_print_progress` on fresh aggregate.
- Reuse `_KEY_TO_NODE` (main.py:49-65) and `_RECURSION_LIMIT` (main.py:43) — unchanged, single source of truth.
- Correct the stale `ANTHROPIC_API_KEY` mention in the module docstring → `OPENROUTER_API_KEY`.

## TDD

### RED — `tests/test_stream_pipeline.py`
Monkeypatch `src.main.build_graph` to return a fake graph whose `.stream()` yields a scripted list of `{node: {state_updates}}` dicts (reuse the stubbing approach in `tests/test_main.py`/`tests/test_graph.py`). Assert:
1. `require_api_key` is called before the graph is built (patch it, assert call order).
2. `on_step` is invoked once per streamed node, receiving `(flat_delta, accumulated_state)` where `accumulated_state` reflects all prior updates merged.
3. Return value equals the fully accumulated `final_state`.
4. No file reads and nothing printed to stdout (capsys empty) when called directly with strings.
5. `run()` still reads files, prints the summary, and returns the same `final_state` (existing `tests/test_main.py` remains green).

### GREEN
Implement `stream_pipeline`; rewrite `run()` as the wrapper. Keep signatures of `run()`, `main()`, `_print_progress`, `_print_summary` intact.

## Acceptance
- `python3 -m pytest tests/test_stream_pipeline.py -q` passes.
- `python3 -m pytest tests/ -q` fully green (CLI regression).
- `grep -n ANTHROPIC_API_KEY src/main.py` returns nothing.

## Files
- `src/main.py` (edit), `tests/test_stream_pipeline.py` (new).
