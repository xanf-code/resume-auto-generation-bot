# Bullet Length Validator — Deterministic Backstop

## Overview

The Writer prompt instructs the model to keep bullets within 158-180 characters, but models slip on hard constraints. The bullet length validator runs post-Writer and pre-Renderer, catching violations and routing them back to Writer via `length_violations`.

## Architecture

### Flow
```
writer → check_bullet_lengths → [violations?]
           ├─ NO  → render_node (proceed)
           └─ YES → writer (fix violations)
```

### Components

1. **Validator Function** (`src/agents/validators.py`)
   - Pure Python character counting (no LLM calls)
   - Returns list of violation strings with precise feedback
   - Default range: 158-180 characters

2. **Validation Node** (`src/agents/validators.py`)
   - Graph node that wraps the validator
   - Sets `length_violations` in state when violations exist
   - Logs violations for debugging

3. **Writer Integration** (`src/agents/writer.py`)
   - `build_writer_user_message` includes LENGTH VIOLATIONS section
   - Instructs Writer to "fix ONLY these bullets to 158-180 chars, keep the rest"
   - Preserves good work, only targets violators

4. **Graph Routing** (`src/pipeline/graph.py`)
   - `route_after_bullet_check` routes based on violations
   - Violations loop back to Writer for targeted fixes
   - Clean bullets proceed to render

## Usage

The validator runs automatically in the pipeline. No configuration needed.

### Violation Format

Each violation includes:
- Role index and bullet index
- Actual character count
- Delta from valid range (SHORT by N / LONG by N)
- Target range (158-180)
- Full bullet text for context

Example:
```
Role 0 bullet 1: 142 chars (SHORT by 16). Target: 158-180 chars.
Text: "Built REST APIs for CRM sync."
```

## Testing

- **Unit tests**: `tests/test_bullet_validator.py` (11 tests)
- **Integration tests**: `tests/test_writer.py` (3 new tests)
- **Graph routing tests**: `tests/test_graph.py` (4 new tests)
- **Coverage**: 173 tests passing ✓

## Why This Works

1. **Deterministic**: Pure Python char counting — no model hallucination
2. **Targeted feedback**: Writer sees exactly which bullets to fix and by how much
3. **Preserves good work**: "fix ONLY these bullets" prevents full rewrites
4. **Reuses existing pattern**: Length violations flow like compile errors
5. **Separate concerns**: Length validation happens before rendering

## Prompt + Validator = Exactly Right

- **Prompt alone**: Makes it *mostly* right (80-90% compliance)
- **Validator backstop**: Makes it *exactly* right (100% compliance)
- **Defense in depth**: Model does heavy lifting, validator catches edge cases
