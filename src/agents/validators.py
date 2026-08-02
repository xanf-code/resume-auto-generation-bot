"""Deterministic validators for Writer output - the bullet-length gate.

The Writer prompt asks the model to keep every experience/project bullet inside
the 195-210 char band, but models slip on hard numeric constraints. This
validator runs post-Writer and pre-Renderer, catching bullets outside the band
and routing them back to Writer via ``length_violations``.

Pure Python validators - no LLM calls, no hallucination, deterministic correctness.
"""
import logging

from src.pipeline.schemas import WriterOutput
from src.pipeline.state import PipelineState
from config.settings import DEFAULT_ROLE_BULLET_COUNTS

log = logging.getLogger(__name__)

# Bullet band - the physical column fits a bullet of this length range.
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

    Checks both role bullets and project bullets (same physical column constraint).

    Args:
        output: The WriterOutput to validate.
        lo: Minimum acceptable bullet length (default: 195 chars).
        hi: Maximum acceptable bullet length (default: 210 chars).

    Returns:
        A list of violation strings (empty if all bullets are valid).
        Each violation includes role/project index, bullet index, actual length,
        delta from range, target band, and the full bullet text for context.
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
    for project in output.projects:
        for i, bullet in enumerate(project.bullets):
            n = len(bullet)
            if not (lo <= n <= hi):
                violations.append(
                    f"Project {project.rank} bullet {i}: {n} chars ({_delta(n, lo, hi)}). "
                    f"Target: {lo}-{hi} chars. Text: {bullet!r}"
                )
    return violations


def validate_bullet_counts(
    output: WriterOutput,
    counts: list[int] | None,
) -> list[str]:
    """Validate that each role's bullet count matches the expected value.

    Only validates roles whose index appears in ``counts``; extra roles emitted
    by the writer beyond the spec length are silently ignored (the writer may
    produce 3 roles when only 2 were budgeted — we don't penalise the overage
    beyond the covered indices).

    Args:
        output: The WriterOutput to validate.
        counts: Expected bullet count per role index. None → DEFAULT_ROLE_BULLET_COUNTS.

    Returns:
        A list of violation strings (empty if all covered roles are in-budget).
    """
    effective = list(counts) if counts else DEFAULT_ROLE_BULLET_COUNTS
    # Build a lookup for fast access; only roles in output are considered.
    bullets_by_index: dict[int, int] = {r.index: len(r.bullets) for r in output.roles}
    violations = []
    for i, expected in enumerate(effective):
        actual = bullets_by_index.get(i)
        if actual is None:
            continue  # role not present — length validator handles missing roles
        if actual == expected:
            continue
        delta = actual - expected
        hint = f"Remove {delta}" if delta > 0 else f"Add {-delta}"
        violations.append(
            f"Role {i}: {actual} bullets, expected EXACTLY {expected}. {hint}."
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
    length_violations = validate_bullet_lengths(output)
    count_violations = validate_bullet_counts(output, state.get("role_bullet_counts"))

    result: dict = {}

    any_violations = length_violations or count_violations

    # Lock project bullets only on a clean first pass: if project_bullets not yet
    # in state, the writer produced project output, and no violations exist.
    # Locking before the violation check would freeze bad bullets and prevent the
    # writer from fixing them (subsequent passes skip ## SELECTED PROJECTS when
    # project_bullets is already in state).
    if not any_violations and not state.get("project_bullets") and output.projects:
        result["project_bullets"] = output.projects

    # Lock the invention ledger on the same clean-first-pass guard: freezing it
    # from a still-violating draft would prevent the writer from revising
    # bullets whose fabrications are about to change.
    if not any_violations and not state.get("invented_stack") and output.invented_stack:
        result["invented_stack"] = output.invented_stack

    result["count_violations"] = count_violations if count_violations else None

    if length_violations:
        retries = state.get("length_retries", 0) + 1
        log.warning(
            "check_bullet_lengths | %d length violation(s) detected (length_retries=%d) "
            "→ routing back to Writer",
            len(length_violations), retries,
        )
        for v in length_violations:
            log.warning("  - %s", v)
        return {**result, "length_violations": length_violations, "length_retries": retries}

    if count_violations:
        log.warning(
            "check_bullet_lengths | %d count violation(s) detected → routing back to Writer",
            len(count_violations),
        )
        for v in count_violations:
            log.warning("  - %s", v)
        return {**result, "length_violations": None}

    log.info(
        "check_bullet_lengths | all bullets within %d-%d chars, counts correct ✓",
        BULLET_LO, BULLET_HI,
    )
    return {**result, "length_violations": None}
