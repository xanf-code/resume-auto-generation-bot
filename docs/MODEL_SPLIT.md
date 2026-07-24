# Model Split Architecture

## Overview
The resume-bot pipeline now uses **four distinct models** to eliminate bias and optimize cost/performance for each specialized task.

## Model Assignments

| Model | Provider | Use Case | Phase | Rationale |
|-------|----------|----------|-------|-----------|
| **Sonnet 5** | Anthropic | Writer | Phase 4 | Creative optimization, nuanced rewriting, keyword balancing |
| **GPT-4o Mini** | OpenAI | Parser + JD Analyzer | Phase 2a | Fast, cheap structured parsing |
| **Opus 4.8** | Anthropic | Gap Analyzer | Phase 2b | Creative reframing strategy requires strong reasoning |
| **GPT-4o Mini** | OpenAI | Scoring Panel | Phase 5 | Independent evaluation (4 recruiters + aggregator) |

## Why Split Models?

### Problem 1: Writer Bias
Previously, both Writer and Scoring Panel used the **same model** (Sonnet 5):
- Writer optimizes resume → Sonnet 5
- Scoring panel evaluates resume → Sonnet 5

**Result:** The scorer is judging its own work. Self-evaluation creates bias — the model tends to score its own output higher.

### Problem 2: Gap Analyzer Needs Strong Reasoning
The Gap Analyzer does **creative reframing work**:
- Takes underrepresented JD competencies
- Maps them to adjacent resume evidence
- Generates concrete framing guidance for the Writer

This requires **strong reasoning and creativity** — not just fast parsing. Using a weak model here produces generic, low-quality framing guidance.

### The Fix
Now:
- **Writer** uses **Sonnet 5** (best creative optimization)
- **Parser + JD Analyzer** use **GPT-4o Mini** (fast, cheap structured extraction)
- **Gap Analyzer** uses **Opus 4.8** (strong reasoning for creative reframing)
- **Scoring panel** uses **GPT-4o Mini** (independent judgment, eliminates bias)

**Result:** 
1. Scorer is a different model architecture — truly independent evaluation
2. Gap Analyzer produces high-quality, creative framing guidance
3. Parser/JD remain fast and cheap for simple extraction

## Code Changes

### 1. Config (`config/settings.py`)
```python
MODEL_STRONG = "anthropic/claude-sonnet-5"  # Writer
MODEL_FAST = "openai/gpt-4o-mini"           # Parser + JD Analyzer
MODEL_GAP = "anthropic/claude-opus-4.8"     # Gap Analyzer
MODEL_SCORING = "openai/gpt-4o-mini"        # Scoring panel
```

### 2. LLM Wrapper (`src/pipeline/llm.py`)
Added `parse_gap()` and `parse_scoring()` functions:
```python
def parse_gap(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the gap analyzer model."""
    model = _ctx_model_gap.get() or MODEL_GAP
    return _parse(system, user, schema, model, max_tokens)

def parse_scoring(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the scoring model (recruiter panel + aggregator)."""
    model = _ctx_model_scoring.get() or MODEL_SCORING
    return _parse(system, user, schema, model, max_tokens)
```

### 3. Gap Analyzer (`src/agents/gap_analyzer.py`)
```python
# Before
from src.pipeline.llm import parse_fast
wrapper = parse_fast(GAP_SYSTEM, user_msg, GapTargets)

# After
from src.pipeline.llm import parse_gap
wrapper = parse_gap(GAP_SYSTEM, user_msg, GapTargets)
```

### 4. Recruiters (`src/agents/recruiters.py`)
```python
# Before
from src.pipeline.llm import parse_strong
score = await asyncio.to_thread(parse_strong, system, user, PanelScore)

# After
from src.pipeline.llm import parse_scoring
score = await asyncio.to_thread(parse_scoring, system, user, PanelScore)
```

### 5. Aggregator (`src/agents/aggregator.py`)
```python
# Before
from src.pipeline.llm import parse_strong
wrapper = parse_strong(DISTILL_NOTES_SYSTEM, user_msg, RevisionNotes)

# After
from src.pipeline.llm import parse_scoring
wrapper = parse_scoring(DISTILL_NOTES_SYSTEM, user_msg, RevisionNotes)
```

### 6. Standalone Scorer (`src/resume_scorer.py`)
```python
# Before
from src.pipeline.llm import parse_strong
parsed_score = parse_strong(system=SYSTEM_PROMPT, user=criteria_user, schema=ResumeScore)

# After
from src.pipeline.llm import parse_scoring
parsed_score = parse_scoring(system=SYSTEM_PROMPT, user=criteria_user, schema=ResumeScore)
```

## Test Updates
All tests updated to mock the correct parsing functions:
- `tests/test_gap_analyzer.py` — mocks `parse_gap` (was `parse_fast`)
- `tests/test_recruiters.py` — mocks `parse_scoring` (was `parse_strong`)
- `tests/test_aggregator.py` — mocks `parse_scoring` (was `parse_strong`)
- `tests/test_resume_scorer.py` — mocks `parse_scoring` (was `parse_strong`)
- `tests/test_settings.py` — checks `MODEL_GAP` and `MODEL_SCORING` constants

**Test Results:** All 155 tests pass ✓

## Benefits

### 1. Eliminates Writer Bias
Independent model architecture (GPT-4o Mini) ensures the scoring panel is not influenced by the Writer's (Sonnet 5) internal representations.

### 2. Higher Quality Gap Analysis
Gap Analyzer now uses **Opus 4.8** instead of GPT-4o Mini:
- Produces **creative, concrete framing guidance** instead of generic suggestions
- Better maps underrepresented JD competencies to adjacent resume evidence
- Writer receives **stronger strategic direction** for reframing bullets

### 3. Cost Optimization
- **Parser + JD Analyzer:** GPT-4o Mini (fast, cheap structured extraction)
- **Gap Analyzer:** Opus 4.8 (worth the cost — quality matters here)
- **Scoring Panel:** GPT-4o Mini (3x cheaper than Sonnet, independent judgment)

### 4. Performance
- Parser/JD remain fast with GPT-4o Mini
- Gap Analyzer quality improved (Opus 4.8 creative reasoning)
- Scoring panel is faster and independent (GPT-4o Mini)
- Writer remains high-quality (Sonnet 5 creative optimization)

## Model Selection Rationale

| Phase | Model | Why This Model? |
|-------|-------|-----------------|
| **Parser** | GPT-4o Mini | Deterministic extraction, fast, cheap — no creativity needed |
| **JD Analyzer** | GPT-4o Mini | Structured skill extraction, keyword matching — simple task |
| **Gap Analyzer** | Opus 4.8 | **Creative reframing strategy** — needs strong reasoning to map competencies to evidence |
| **Writer** | Sonnet 5 | Creative optimization, nuanced keyword balancing, best coding/writing model |
| **Scoring Panel** | GPT-4o Mini | Independent evaluation (different architecture from Writer), cost-effective |

## Future Considerations
If you want even more independence or optimization, consider:
- **A/B testing Gap Analyzer models** — compare Opus 4.8 vs Sonnet 5 quality
- **Ensemble scoring** — use multiple independent models for scoring panel
- **Dynamic model routing** — choose model based on task complexity (e.g., simple JDs → GPT-4o Mini gap analyzer)

---

**Implementation Date:** 2026-07-23  
**Status:** ✓ Complete — All 155 tests passing, E2E test passed with 86.44 aggregate score
