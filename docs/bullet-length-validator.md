# Bullet Length Validator — Deterministic Backstop

## Overview

The Writer prompt instructs the model to keep every experience/project bullet within **195-210 characters** (minimum 195, maximum 210), but models slip on hard numeric constraints. The bullet length validator runs post-Writer and pre-Renderer, catching violations and routing them back to Writer via `length_violations`.

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
   - `validate_bullet_lengths` — default `BULLET_LO=195` / `BULLET_HI=210`
   - Returns a list of violation strings with precise feedback

2. **Validation Node** (`src/agents/validators.py`)
   - `check_bullet_lengths` wraps the validator
   - Sets `length_violations` in state when violations exist
   - Logs violations for debugging

3. **Writer Integration** (`src/agents/writer.py`)
   - `build_writer_user_message` includes a LENGTH VIOLATIONS section
   - Instructs Writer to "fix ONLY these bullets to 195-210 chars, keep the rest"
   - Preserves good work, only targets violators

4. **Graph Routing** (`src/pipeline/graph.py`)
   - `route_after_bullet_check` routes based on violations
   - Violations loop back to Writer for targeted fixes
   - Clean bullets proceed to render

## Usage

The validator runs automatically in the pipeline. No configuration needed.

### Violation Format

Each violation includes the role/bullet index, actual character count, the delta from the valid range (`UNDERBUILT by N` / `BLOATED by N`), the target band, and the full bullet text for context.

Example:
```
Role 0 bullet 1: 142 chars (UNDERBUILT by 53). Target: 195-210 chars.
Text: "Built REST APIs for CRM sync."
```

## Testing

- **Unit tests**: `tests/test_bullet_validator.py`
- **Integration tests**: `tests/test_writer.py` (LENGTH VIOLATIONS section, prompt band)
- **Graph routing tests**: `tests/test_graph.py` (routing + compile page-overflow remedy)

## Why This Works

1. **Deterministic**: Pure Python char counting — no model hallucination
2. **Targeted feedback**: Writer sees exactly which bullets to fix and by how much
3. **Preserves good work**: "fix ONLY these bullets" prevents full rewrites
4. **Reuses existing pattern**: Length violations flow like compile errors
5. **Separate concerns**: Length validation happens before rendering

## Page Overflow

Because bullets are fixed to the 195-210 band, they cannot be shortened below 195 to save space. When the compile step reports >1 page, the retry remedy therefore targets bullet **COUNT** (drop the lowest-value bullet from the role with the most, within the 8-total / 5-per-role caps) and trims the skills list — never "shorten the bullets."
