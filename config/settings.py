"""Global configuration constants for resume-bot.

Constants live at module level and NEVER require the API key to import.
The API key is resolved lazily via ``require_api_key`` so that importing this
module (and the whole package) works in test/CI environments without a key.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Loop / scoring thresholds ------------------------------------------------
THRESHOLD = 78          # lowered from 88 - fabrication mode; plausibility caps ~85
# Tightened from 6/4/4 - the writer loop (MODEL_STRONG) is the dominant
# pipeline cost. On cap-hit the pipeline already ships the best-scoring draft
# seen so far, so a smaller worst-case tail trims cost with near-zero
# happy-path pass-rate impact.
MAX_ITERATIONS = 4
MAX_COMPILE_RETRIES = 2
MAX_IDENTITY_RETRIES = 2
# Per-iteration budget for the bullet-length loop. On exhaustion the pipeline
# proceeds to render with the best-effort draft (never blocks on a cosmetic
# gate), guaranteeing the writer↔check loop can't spin forever.
MAX_LENGTH_RETRIES = 3
PLAUSIBILITY_FLOOR = 20

# --- Rubric weights (must sum to 1.0) ----------------------------------------
# Swapped plausibility ↔ keyword_match vs original design.
# In fabrication mode, keyword coverage is the primary signal; plausibility
# will always be suppressed by adjacent-framing claims and should not anchor.
RUBRIC_WEIGHTS = {
    "keyword_match":  0.30,   # was 0.20 - ATS coverage is the optimization target
    "impact_quality": 0.20,
    "coherence":      0.20,   # was 0.15 - narrative coherence matters more than plausibility
    "plausibility":   0.15,   # was 0.30 - deprioritized; fabrication mode
    "formatting":     0.15,
}

# --- Model identifiers --------------------------------------------------------
# OpenRouter-namespaced slugs (provider/model).
# - MODEL_STRONG: Writer (creative optimization, keyword balancing, effort=high)
# - MODEL_FAST: Parser + JD Analyzer (fast structured extraction, effort=low)
# - MODEL_GAP: Gap Analyzer (creative reframing strategy, needs strong reasoning, effort=high)
# - MODEL_SCORING: Scoring panel (independent evaluation, eliminates writer bias, effort=low)
MODEL_STRONG = "anthropic/claude-sonnet-5"
MODEL_FAST = "openai/gpt-4o-mini"
MODEL_GAP = "anthropic/claude-opus-5"
MODEL_SCORING = "openai/gpt-4o-mini"
MODEL_SKILLS = "openai/gpt-4o-mini"

# --- Reasoning effort ----------------------------------------------------------
# Forwarded to OpenRouter's unified `reasoning` parameter
# (extra_body={"reasoning": {"effort": ...}}), which Anthropic reasoning models
# honor as thinking-effort depth. Only MODEL_STRONG / MODEL_GAP are reasoning
# models - MODEL_FAST / MODEL_SCORING (gpt-4o-mini) don't take an effort knob.
# Valid values: "low" | "medium" | "high" | "max" | "x-high".
EFFORT_STRONG = "medium"  # Writer (creative optimization, keyword balancing)
EFFORT_GAP = "medium"     # Gap Analyzer (creative reframing strategy)
EFFORT_SKILLS = "low"     # Skills node (ignored by gpt-4o-mini; wired for future reasoning-model switch)

_API_KEY_ENV = "OPENROUTER_API_KEY"


def require_api_key() -> str:
    """Return the OpenRouter API key from the environment.

    Raises:
        RuntimeError: if ``OPENROUTER_API_KEY`` is missing or empty. This is the
            "raise at startup if missing" guarantee - enforced when the key is
            actually needed, never at import time.
    """
    key = os.environ.get(_API_KEY_ENV, "")
    if not key:
        raise RuntimeError(
            f"{_API_KEY_ENV} is not set. Export it before running the pipeline."
        )
    return key
