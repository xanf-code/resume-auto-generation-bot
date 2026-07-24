"""Global configuration constants for resume-bot.

Constants live at module level and NEVER require the API key to import.
The API key is resolved lazily via ``require_api_key`` so that importing this
module (and the whole package) works in test/CI environments without a key.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Loop / scoring thresholds ------------------------------------------------
THRESHOLD = 78          # lowered from 88 — fabrication mode; plausibility caps ~85
MAX_ITERATIONS = 6
MAX_COMPILE_RETRIES = 4
MAX_IDENTITY_RETRIES = 4
PLAUSIBILITY_FLOOR = 20

# --- Rubric weights (must sum to 1.0) ----------------------------------------
# Swapped plausibility ↔ keyword_match vs original design.
# In fabrication mode, keyword coverage is the primary signal; plausibility
# will always be suppressed by adjacent-framing claims and should not anchor.
RUBRIC_WEIGHTS = {
    "keyword_match":  0.30,   # was 0.20 — ATS coverage is the optimization target
    "impact_quality": 0.20,
    "coherence":      0.20,   # was 0.15 — narrative coherence matters more than plausibility
    "plausibility":   0.15,   # was 0.30 — deprioritized; fabrication mode
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
MODEL_GAP = "anthropic/claude-opus-4.8"
MODEL_SCORING = "openai/gpt-4o-mini"

_API_KEY_ENV = "OPENROUTER_API_KEY"


def require_api_key() -> str:
    """Return the OpenRouter API key from the environment.

    Raises:
        RuntimeError: if ``OPENROUTER_API_KEY`` is missing or empty. This is the
            "raise at startup if missing" guarantee — enforced when the key is
            actually needed, never at import time.
    """
    key = os.environ.get(_API_KEY_ENV, "")
    if not key:
        raise RuntimeError(
            f"{_API_KEY_ENV} is not set. Export it before running the pipeline."
        )
    return key
