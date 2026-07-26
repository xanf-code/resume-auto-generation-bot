"""Tuning resolver - the Loop B apply side.

Merges ``vault/tuning/active.json``'s sparse per-tag overrides onto the frozen
``config/settings.py`` defaults (via :class:`~src.pipeline.tuning.PipelineTuning`)
for the current run. ``settings.py`` is never written - ``active.json`` is a
deletable, diffable override layered on top, approved by a human editing the
vault (see ``docs/obsidian/phase-8-proposal-cli.md`` for how proposals land
there).
"""
from __future__ import annotations

import json
from typing import Any

from src.pipeline.tuning import RUBRIC_KEYS, PipelineTuning
from src.vault.config import VaultSettings

_SCALAR_FIELDS: tuple[str, ...] = (
    "threshold",
    "plausibility_floor",
    "max_iterations",
    "max_compile_retries",
    "max_identity_retries",
    "max_length_retries",
)


def _load_by_tag(settings: VaultSettings) -> dict[str, Any]:
    """Read ``tuning/active.json``'s ``by_tag`` map, or ``{}`` on any problem."""
    if not settings.enabled or settings.dir is None:
        return {}

    path = settings.dir / "tuning" / "active.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

    by_tag = raw.get("by_tag") if isinstance(raw, dict) else None
    return by_tag if isinstance(by_tag, dict) else {}


def _best_match(by_tag: dict[str, Any], tags: list[str]) -> dict | None:
    """Return the most-specific entry whose `+`-joined tag key ⊆ *tags*."""
    run_tags = set(tags)
    matches = [
        key
        for key in by_tag
        if isinstance(by_tag.get(key), dict) and set(key.split("+")) <= run_tags
    ]
    if not matches:
        return None

    best_key = max(matches, key=lambda key: (len(key.split("+")), key))
    return by_tag[best_key]


def _merge_rubric_weights(base_weights, override: Any) -> dict[str, float]:
    """Overlay *override* onto *base_weights* and renormalize to sum 1.0."""
    merged = dict(base_weights)
    if isinstance(override, dict):
        for key in RUBRIC_KEYS:
            if key in override:
                merged[key] = override[key]

    total = sum(merged.values())
    if total > 0:
        merged = {key: value / total for key, value in merged.items()}
    return merged


def resolve_tuning(
    tags: list[str], base: PipelineTuning | None, *, settings: VaultSettings
) -> tuple[PipelineTuning, dict]:
    """Resolve the effective tuning for *tags*, plus a diff for the activity log.

    *base* is ``job.tuning`` when the user set knobs in the UI this run - that
    explicit choice always wins and is returned unchanged. Otherwise the base is
    ``PipelineTuning.defaults()`` and the vault's most-specific matching
    ``by_tag`` entry (if any) is merged onto it.
    """
    if base is not None:
        return base, {}

    resolved_base = PipelineTuning.defaults()
    by_tag = _load_by_tag(settings)
    entry = _best_match(by_tag, tags)
    if entry is None:
        return resolved_base, {}

    diff: dict[str, tuple] = {}

    field_values = {field: getattr(resolved_base, field) for field in _SCALAR_FIELDS}
    for field in _SCALAR_FIELDS:
        if field in entry and entry[field] != field_values[field]:
            diff[field] = (field_values[field], entry[field])
            field_values[field] = entry[field]

    rubric_weights = _merge_rubric_weights(resolved_base.rubric_weights, entry.get("rubric_weights"))
    if rubric_weights != dict(resolved_base.rubric_weights):
        diff["rubric_weights"] = (dict(resolved_base.rubric_weights), rubric_weights)

    tuning = PipelineTuning(
        threshold=field_values["threshold"],
        plausibility_floor=field_values["plausibility_floor"],
        max_iterations=field_values["max_iterations"],
        max_compile_retries=field_values["max_compile_retries"],
        max_identity_retries=field_values["max_identity_retries"],
        max_length_retries=field_values["max_length_retries"],
        rubric_weights=rubric_weights,
    )
    return tuning, diff
