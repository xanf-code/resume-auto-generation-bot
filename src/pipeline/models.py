"""Per-run model selection for pipeline LLM roles.

Historically writer / parser / gap / scoring models lived as module constants in
``config.settings``. ``PipelineModels`` lifts them into an immutable per-run
config so the New Application UI can override models (and optional reasoning
effort) without mutating globals.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import settings


KNOWN_EFFORTS: frozenset[str] = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "max"}
)


@dataclass(frozen=True)
class ModelRole:
    """One pipeline role's model slug and optional reasoning effort."""

    model: str
    effort: str | None = None


@dataclass(frozen=True)
class PipelineModels:
    """Immutable per-run model config for the four user-facing LLM roles."""

    writer: ModelRole
    parser: ModelRole
    gap: ModelRole
    scoring: ModelRole

    @classmethod
    def defaults(cls) -> "PipelineModels":
        """Build from ``config.settings`` MODEL_* / EFFORT_* constants."""
        return cls(
            writer=ModelRole(settings.MODEL_STRONG, settings.EFFORT_STRONG),
            parser=ModelRole(settings.MODEL_FAST, None),
            gap=ModelRole(settings.MODEL_GAP, settings.EFFORT_GAP),
            scoring=ModelRole(settings.MODEL_SCORING, None),
        )
