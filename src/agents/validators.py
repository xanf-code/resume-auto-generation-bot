"""Deterministic validators for Writer output — the bullet-length gate.

The Writer prompt asks the model to keep every experience/project bullet inside
the 195-210 char band, but models slip on hard numeric constraints. This
validator runs post-Writer and pre-Renderer, catching bullets outside the band
and routing them back to Writer via ``length_violations``.

Pure Python validators — no LLM calls, no hallucination, deterministic correctness.
"""
import logging

from src.pipeline.schemas import WriterOutput
from src.pipeline.state import PipelineState

log = logging.getLogger(__name__)

# Bullet band — the physical column fits a bullet of this length range.
BULLET_LO = 195
BULLET_HI = 210


def _delta(n: int, lo: int, hi: int) -> str:
    """Human-readable distance from the [lo, hi] band for a length ``n``."""
    return f"UNDERBUILT by {lo - n}" if n < lo else f"BLOATED by {n - hi}"


def validate_bullet_lengths(
    output: WriterOutput,
    lo: int = BULLET_LO,
    hi: int = BULLET_HI,
) -> list[str]:
    """Validate bullet lengths are within [lo, hi] character range.

    Args:
        output: The WriterOutput to validate.
        lo: Minimum acceptable bullet length (default: 195 chars).
        hi: Maximum acceptable bullet length (default: 210 chars).

    Returns:
        A list of violation strings (empty if all bullets are valid).
        Each violation includes role index, bullet index, actual length,
        delta from range, target band, and the full bullet text for context.

    Example violation::

        Role 0 bullet 1: 142 chars (UNDERBUILT by 53). Target: 195-210 chars.
        Text: "Built REST APIs for CRM sync."
    """
    violations = []
    for role in output.roles:
        for i, bullet in enumerate(role.bullets):
            n = len(bullet)
            if not (lo <= n <= hi):
                violations.append(
                    f"Role {role.index} bullet {i}: {n} chars ({_delta(n, lo, hi)}). "
                    f"Target: {lo}-{hi} chars. Text: {bullet!r}"
                )
    return violations


def check_bullet_lengths(state: PipelineState) -> dict:
    """Node: validate bullet lengths and set ``length_violations`` if any fail.

    Runs post-Writer and pre-Renderer. If violations exist, they route back to
    Writer via the ``length_violations`` state key (similar to compile_errors),
    and ``length_retries`` is incremented so ``route_after_bullet_check`` can
    stop the writer↔check loop once the budget is spent.

    The Writer's user-message builder includes a LENGTH VIOLATIONS section when
    this key is present, instructing it to fix ONLY the violating bullets.

    On a clean pass, ``length_retries`` is intentionally omitted from the return
    so the per-iteration counter is preserved (LangGraph only overwrites keys
    present in the returned dict).
    """
    output = state["writer_output"]
    violations = validate_bullet_lengths(output)

    if violations:
        retries = state.get("length_retries", 0) + 1
        log.warning(
            "check_bullet_lengths | %d violation(s) detected (length_retries=%d) "
            "→ routing back to Writer",
            len(violations), retries,
        )
        for v in violations:
            log.warning("  - %s", v)
        return {"length_violations": violations, "length_retries": retries}

    log.info(
        "check_bullet_lengths | all bullets within %d-%d chars ✓",
        BULLET_LO, BULLET_HI,
    )
    return {"length_violations": None}
