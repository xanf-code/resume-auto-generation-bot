# Phase 0 — Setup & Skeleton

**Goal:** Toolchain installed, dependencies pinned, empty project skeleton in place.
No LLM or logic yet — just make everything importable and compilable.

## Tasks

1. **Install tectonic** (currently NOT on the machine):
   ```bash
   brew install tectonic
   tectonic --version   # verify
   ```
2. **Create `requirements.txt`:**
   ```
   langgraph>=0.2
   anthropic>=0.40
   pydantic>=2
   jinja2>=3
   pytest>=8
   ```
   ```bash
   pip3 install -r requirements.txt
   ```
3. **Scaffold directories** (matching the plan layout):
   ```
   src/{pipeline,agents,prompts,compiler,templates}/
   config/  tests/  examples/  out/
   ```
   Add `__init__.py` to every `src/*` package dir.
4. **`config/settings.py`** — constants only:
   - `THRESHOLD = 88`, `MAX_ITERATIONS = 6`, `MAX_COMPILE_RETRIES = 2`,
     `PLAUSIBILITY_FLOOR = 70`
   - `RUBRIC_WEIGHTS = {"plausibility": 0.30, "keyword_match": 0.20,
     "impact_quality": 0.20, "coherence": 0.15, "formatting": 0.15}`
   - `MODEL_STRONG = "claude-opus-4-8"`, `MODEL_FAST = "claude-haiku-4-5"`
   - Read `ANTHROPIC_API_KEY` from env; raise at startup if missing.
     **Never hardcode the key.**

## Exit criteria

- `tectonic --version` works.
- `python3 -c "import langgraph, anthropic, pydantic, jinja2"` succeeds.
- `python3 -c "import config.settings"` succeeds and exposes the constants.
- Directory tree matches the plan; no stray files in repo root.
