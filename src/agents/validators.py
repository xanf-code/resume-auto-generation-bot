"""Deterministic validators for Writer output — bullet length backstop.

The Writer prompt instructs the model to keep bullets within 195-210 chars
(200-205 ideal), but models slip on hard constraints. These validators run
post-Writer and pre-Renderer, catching violations and routing them back to
Writer via ``length_violations``.

Pure Python validators — no LLM calls, no hallucination, deterministic correctness.
"""
import logging

from src.pipeline.schemas import WriterOutput
from src.pipeline.state import PipelineState

log = logging.getLogger(__name__)

DEFAULT_LO = 195
DEFAULT_HI = 210


def validate_bullet_lengths(
    output: WriterOutput,
    lo: int = DEFAULT_LO,
    hi: int = DEFAULT_HI,
) -> list[str]:
    """Validate bullet lengths are within [lo, hi] character range.

    Args:
        output: The WriterOutput to validate.
        lo: Minimum acceptable bullet length (default: 195 chars).
        hi: Maximum acceptable bullet length (default: 210 chars).

    Returns:
        A list of violation strings (empty if all bullets are valid).
        Each violation includes role index, bullet index, actual length,
        delta from range, and the full bullet text for debugging context.

    Example violation::

        Role 0 bullet 1: 142 chars (UNDERBUILT by 53). Target: 195-210 chars.
        Text: "Built REST APIs for CRM sync."
    """
    violations = []
    for role in output.roles:
        for i, bullet in enumerate(role.bullets):
            n = len(bullet)
            if not (lo <= n <= hi):
                delta = f"UNDERBUILT by {lo - n}" if n < lo else f"BLOATED by {n - hi}"
                violations.append(
                    f"Role {role.index} bullet {i}: {n} chars ({delta}). "
                    f"Target: {lo}-{hi} chars, aim for 200-205. Text: {bullet!r}"
                )
    return violations


def check_bullet_lengths(state: PipelineState) -> dict:
    """Node: validate bullet lengths and set length_violations if any fail.

    Runs post-Writer and pre-Renderer. If violations exist, they route back to
    Writer via the ``length_violations`` state key (similar to compile_errors).

    The Writer's user-message builder includes a LENGTH VIOLATIONS section when
    this key is present, instructing it to fix ONLY the violating bullets.
    """
    output = state["writer_output"]
    violations = validate_bullet_lengths(output)

    if violations:
        log.warning(
            "check_bullet_lengths | %d violation(s) detected → routing back to Writer",
            len(violations),
        )
        for v in violations:
            log.warning("  - %s", v)
    else:
        log.info("check_bullet_lengths | all bullets within %d-%d chars ✓",
                 DEFAULT_LO, DEFAULT_HI)

    return {"length_violations": violations if violations else None}
