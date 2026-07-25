"""PipelineTuning - the per-run knobs that were once fixed module constants.

Historically the scoring threshold, plausibility floor, loop/retry budgets, and
rubric weights lived as constants in :mod:`config.settings` and were read
directly at import time by the aggregator, graph routers, and progress math.
That made them global - every run used the same values.

``PipelineTuning`` lifts those knobs into an immutable per-run config carried on
the pipeline state (``state["tuning"]``). Nodes read it via :func:`get_tuning`,
which falls back to :meth:`PipelineTuning.defaults` - sourced from the very same
``config.settings`` constants - so a run that supplies no config behaves exactly
as before.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from config import settings

# The five rubric dimensions, in a stable order. Kept here (not derived from a
# dict at call time) so callers have one canonical tuple to iterate.
RUBRIC_KEYS: tuple[str, ...] = (
    "keyword_match",
    "impact_quality",
    "coherence",
    "plausibility",
    "formatting",
)


@dataclass(frozen=True)
class PipelineTuning:
    """Immutable per-run tuning config.

    ``rubric_weights`` is stored as a read-only mapping and is expected to sum to
    1.0 (the aggregate is compared against ``threshold`` on a 0–100 scale, so the
    weights must be normalized for the threshold semantics to hold). Normalization
    happens at the web boundary (:class:`TuningDTO`); this dataclass trusts its
    inputs.
    """

    threshold: int
    plausibility_floor: int
    max_iterations: int
    max_compile_retries: int
    max_identity_retries: int
    max_length_retries: int
    rubric_weights: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType(dict(settings.RUBRIC_WEIGHTS))
    )

    @classmethod
    def defaults(cls) -> "PipelineTuning":
        """Build the config from the current ``config.settings`` constants."""
        return cls(
            threshold=settings.THRESHOLD,
            plausibility_floor=settings.PLAUSIBILITY_FLOOR,
            max_iterations=settings.MAX_ITERATIONS,
            max_compile_retries=settings.MAX_COMPILE_RETRIES,
            max_identity_retries=settings.MAX_IDENTITY_RETRIES,
            max_length_retries=settings.MAX_LENGTH_RETRIES,
            rubric_weights=MappingProxyType(dict(settings.RUBRIC_WEIGHTS)),
        )


def get_tuning(state: Mapping) -> PipelineTuning:
    """Return the run's tuning from *state*, or the defaults when absent.

    Accepts any mapping (the pipeline ``PipelineState`` TypedDict, or a plain
    dict in tests). ``{"tuning": None}`` - the shape a caller that passes no
    config produces - resolves to the defaults, not a crash.
    """
    tuning = state.get("tuning")
    if isinstance(tuning, PipelineTuning):
        return tuning
    return PipelineTuning.defaults()
