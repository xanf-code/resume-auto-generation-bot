"""Aggregator - the quality gate. Pure-code scoring, one Opus call only on fail.

Scoring is deterministic Python: each persona's five rubric dimensions collapse
to a weighted composite (``RUBRIC_WEIGHTS``), the four composites average to the
``aggregate_score``, and the decision is a pure boolean:

    PASS  <=>  aggregate_score >= THRESHOLD  AND  skeptic plausibility >= FLOOR

The plausibility FLOOR is the fabrication guard: a resume can score high overall
yet still be rejected if the Skeptic doubts its truthfulness.

The ONLY LLM call in this module is ``distill_revision_notes``, and it fires
ONLY on the fail path - collapsing the four personas' free-text notes into a
ranked, deduplicated directive list for the Writer's next iteration.
"""
import logging
from typing import Mapping

from config.settings import MODEL_SCORING, PLAUSIBILITY_FLOOR, RUBRIC_WEIGHTS, THRESHOLD

log = logging.getLogger(__name__)
from src.pipeline.llm import parse_scoring
from src.pipeline.schemas import PanelScore, RevisionNotes
from src.pipeline.state import PipelineState
from src.pipeline.tuning import get_tuning
from src.prompts.recruiters import DISTILL_NOTES_SYSTEM

_SKEPTIC = "Skeptic"


def persona_composite(
    score: PanelScore, weights: Mapping[str, float] | None = None
) -> float:
    """Weighted mean of one persona's rubric dimensions (weights sum to 1.0).

    *weights* defaults to the global ``RUBRIC_WEIGHTS`` so callers that don't
    tune the panel keep the historical behaviour.
    """
    w = weights if weights is not None else RUBRIC_WEIGHTS
    return (
        w["plausibility"] * score.plausibility
        + w["keyword_match"] * score.keyword_match
        + w["impact_quality"] * score.impact_quality
        + w["coherence"] * score.coherence
        + w["formatting"] * score.formatting
    )


def aggregate(
    scores: list[PanelScore], weights: Mapping[str, float] | None = None
) -> float:
    """Mean of the four persona composites."""
    composites = [persona_composite(s, weights) for s in scores]
    return sum(composites) / len(composites)


def skeptic_plausibility(scores: list[PanelScore]) -> int:
    """The Skeptic persona's raw plausibility score.

    Raises:
        ValueError: if no Skeptic persona is present in the panel.
    """
    for s in scores:
        if s.persona == _SKEPTIC:
            return s.plausibility
    raise ValueError("Panel is missing the Skeptic persona.")


def decide(
    scores: list[PanelScore],
    threshold: float | None = None,
    floor: float | None = None,
    weights: Mapping[str, float] | None = None,
) -> tuple[bool, float]:
    """Return ``(passed, aggregate_score)``.

    PASS requires BOTH the aggregate to clear *threshold* AND the Skeptic's
    plausibility to clear *floor*. The floor vetoes an otherwise passing
    aggregate - the fabrication guard. All three tuning inputs default to the
    global constants so an untuned call is unchanged.
    """
    thr = threshold if threshold is not None else THRESHOLD
    flr = floor if floor is not None else PLAUSIBILITY_FLOOR
    agg = aggregate(scores, weights)
    passed = agg >= thr and skeptic_plausibility(scores) >= flr
    return passed, agg


def _build_distill_user_message(scores: list[PanelScore]) -> str:
    """Assemble the persona notes into the distillation prompt payload."""
    blocks = [
        f"### {s.persona}\n{s.notes}"
        for s in scores
    ]
    return "## PERSONA NOTES (to distill into ranked directives)\n\n" + "\n\n".join(
        blocks
    ) + "\n"


def distill_revision_notes(scores: list[PanelScore]) -> list[str]:
    """The ONLY LLM call: collapse persona notes into ranked directives.

    Made only on the fail path. Returns a plain list of directive strings,
    unwrapped from the ``RevisionNotes`` model.
    """
    user_msg = _build_distill_user_message(scores)
    wrapper = parse_scoring(DISTILL_NOTES_SYSTEM, user_msg, RevisionNotes)
    return list(wrapper.notes)


def aggregator(state: PipelineState) -> dict:
    """Node: score the panel, decide pass/fail, distill notes only on fail.

    Threshold, plausibility floor, and rubric weights come from the run's
    ``tuning`` (falling back to the ``config.settings`` defaults).
    """
    tuning = get_tuning(state)
    weights = tuning.rubric_weights
    scores = state["panel_scores"]
    for s in scores:
        comp = persona_composite(s, weights)
        log.info("aggregator   | %-22s composite=%.2f", s.persona, comp)
    passed, agg = decide(
        scores,
        threshold=tuning.threshold,
        floor=tuning.plausibility_floor,
        weights=weights,
    )
    sp = skeptic_plausibility(scores)
    log.info(
        "aggregator   | aggregate=%.2f  skeptic_plausibility=%d  "
        "threshold=%d  floor=%d  → %s",
        agg, sp, tuning.threshold, tuning.plausibility_floor,
        "PASS ✓" if passed else "FAIL ✗",
    )

    result = {
        "panel_scores": scores,
        "aggregate_score": agg,
        "passed": passed,
    }
    if not passed:
        log.info("aggregator   | distilling revision notes via %s…", MODEL_SCORING)
        result["revision_notes"] = distill_revision_notes(scores)
        log.info("aggregator   | %d revision directives ready", len(result["revision_notes"]))
    return result
