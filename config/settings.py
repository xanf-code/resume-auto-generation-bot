"""Global configuration constants for resume-bot.

Constants live at module level and NEVER require the API key to import.
The API key is resolved lazily via ``require_api_key`` so that importing this
module (and the whole package) works in test/CI environments without a key.
"""
import os

# --- Loop / scoring thresholds ------------------------------------------------
THRESHOLD = 88
MAX_ITERATIONS = 6
MAX_COMPILE_RETRIES = 2
PLAUSIBILITY_FLOOR = 70

# --- Rubric weights (must sum to 1.0) ----------------------------------------
RUBRIC_WEIGHTS = {
    "plausibility": 0.30,
    "keyword_match": 0.20,
    "impact_quality": 0.20,
    "coherence": 0.15,
    "formatting": 0.15,
}

# --- Model identifiers --------------------------------------------------------
MODEL_STRONG = "claude-opus-4-8"
MODEL_FAST = "claude-haiku-4-5"

_API_KEY_ENV = "ANTHROPIC_API_KEY"


def require_api_key() -> str:
    """Return the Anthropic API key from the environment.

    Raises:
        RuntimeError: if ``ANTHROPIC_API_KEY`` is missing or empty. This is the
            "raise at startup if missing" guarantee — enforced when the key is
            actually needed, never at import time.
    """
    key = os.environ.get(_API_KEY_ENV, "")
    if not key:
        raise RuntimeError(
            f"{_API_KEY_ENV} is not set. Export it before running the pipeline."
        )
    return key
