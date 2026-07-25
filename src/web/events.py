"""Translate raw pipeline stream deltas into ProgressEvent DTOs.

This module is pure (no I/O, no threading). It imports ``_KEY_TO_NODE``
from ``src.main`` to stay in sync with the pipeline's node labeling without
duplicating the mapping.
"""
from __future__ import annotations

from src.main import _KEY_TO_NODE
from config.settings import MAX_ITERATIONS
from src.web.schemas import PersonaScoreDTO, ProgressEvent

# ---------------------------------------------------------------------------
# Human-readable labels per node name
# ---------------------------------------------------------------------------

STAGE_LABELS: dict[str, str] = {
    "parse_resume":    "Parsing resume",
    "analyze_jd":      "Analyzing job description",
    "gap_analysis":    "Running gap analysis",
    "generate_skills": "Generating skill dump",
    "writer":          "Writing bullets (iteration {iteration})",
    "render":          "Rendering LaTeX",
    "identity_check":  "Checking identity integrity",
    "compile":         "Compiling PDF",
    "recruiter_panel": "Recruiter panel scoring",
    "aggregator":      "Aggregating scores",
    "bookkeep":        "Bookkeeping best iteration",
    "emit":            "Emitting artifacts",
    "score_report":    "Writing score report",
}

# ---------------------------------------------------------------------------
# Monotonic percentage heuristic
# ---------------------------------------------------------------------------

_SPINE: list[str] = [
    "parse_resume", "analyze_jd", "gap_analysis", "generate_skills",
]
_LOOP: list[str] = [
    "writer", "render", "identity_check", "compile",
    "recruiter_panel", "aggregator", "bookkeep",
]

_SPINE_START = 0
_SPINE_END = 25       # spine covers 0-24%
_LOOP_START = 25
_LOOP_END = 90        # loop covers 25-89%
_EMIT_PCT = 90


def pct_estimate(stage: str, iteration: int, max_iterations: int = MAX_ITERATIONS) -> int:
    """Return an integer 0-100 estimate of pipeline progress.

    Guarantees: non-decreasing as (stage, iteration) advances along the
    normal execution path. *max_iterations* scales how the writer loop's 25–90%
    band is divided so the bar paces correctly when a run tunes the loop budget;
    it defaults to the global ``MAX_ITERATIONS`` for untuned callers.
    """
    if stage in _SPINE:
        idx = _SPINE.index(stage)
        return int(_SPINE_START + idx * (_SPINE_END - _SPINE_START) / len(_SPINE))

    if stage == "emit" or stage == "score_report":
        return _EMIT_PCT

    if stage in _LOOP:
        # Guard against a zero/negative budget dividing the loop band.
        iters = max(max_iterations, 1)
        loop_range = _LOOP_END - _LOOP_START          # 65
        per_iter = loop_range / iters
        per_node = per_iter / len(_LOOP)
        node_idx = _LOOP.index(stage)
        return int(_LOOP_START + (iteration - 1) * per_iter + node_idx * per_node)

    return 0


# ---------------------------------------------------------------------------
# Delta → ProgressEvent
# ---------------------------------------------------------------------------

def build_progress_event(
    job_id: str,
    flat_delta: dict,
    state: dict,
) -> ProgressEvent | None:
    """Translate one stream delta into a ProgressEvent, or None if unrecognised.

    Uses the first matching key in ``_KEY_TO_NODE`` - same priority order as
    the dict definition in ``src.main``.
    """
    stage: str | None = None
    for key, node in _KEY_TO_NODE.items():
        if key in flat_delta:
            stage = node
            break

    if stage is None:
        return None

    iteration: int = int(state.get("iteration", 1))

    # Pace the writer-loop band by the run's tuned iteration budget when present.
    tuning = state.get("tuning")
    max_iterations = getattr(tuning, "max_iterations", MAX_ITERATIONS)

    # Resolve human label; writer label interpolates iteration number.
    raw_label = STAGE_LABELS.get(stage, stage)
    human_label = raw_label.format(iteration=iteration) if "{iteration}" in raw_label else raw_label

    # Persona scores only when panel_scores is in this delta.
    persona_scores = None
    if "panel_scores" in flat_delta:
        persona_scores = [
            PersonaScoreDTO(
                persona=ps.persona,
                keyword_match=ps.keyword_match,
                impact_quality=ps.impact_quality,
                coherence=ps.coherence,
                plausibility=ps.plausibility,
                formatting=ps.formatting,
                notes=ps.notes,
            )
            for ps in flat_delta["panel_scores"]
        ]

    return ProgressEvent(
        job_id=job_id,
        stage=stage,
        human_label=human_label,
        pct=pct_estimate(stage, iteration, max_iterations),
        iteration=iteration,
        aggregate_score=state.get("aggregate_score"),
        passed=state.get("passed"),
        persona_scores=persona_scores,
    )
