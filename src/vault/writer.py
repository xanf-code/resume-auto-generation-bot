"""Run-note writer - the unit of vault memory for one pipeline run.

``write_run_note`` writes ``runs/<date>-<slug>.md`` capturing the facts the
learning loop needs (frontmatter) and the bullets it will reuse (the
``## Final bullets`` body). A no-op when the vault is disabled.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipeline.emit import build_score_report
from src.pipeline.tuning import RUBRIC_KEYS, get_tuning
from src.vault.config import VaultSettings
from src.vault.notes import read_note, write_note

_ITEM_RE = re.compile(r"\\item\s+(.*)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(label: str) -> str:
    """Filesystem-safe slug: lowercase, non-alnum runs collapsed to one dash."""
    slug = _SLUG_RE.sub("-", label.lower()).strip("-")
    return slug or "untitled"


def _bullets_from_writer_output(final_state: dict) -> list[str]:
    writer_output = final_state.get("writer_output")
    if writer_output is None:
        return []
    return [bullet for role in writer_output.roles for bullet in role.bullets]


def _bullets_from_latex(latex: str) -> list[str]:
    """Fallback parse: pull ``\\item`` lines out of a rendered LaTeX resume."""
    return [match.group(1).strip() for match in _ITEM_RE.finditer(latex)]


def _final_bullets(final_state: dict) -> list[str]:
    bullets = _bullets_from_writer_output(final_state)
    if bullets:
        return bullets
    return _bullets_from_latex(final_state.get("best_latex") or "")


def _persona_composite(persona: dict, weights) -> float:
    return sum(weights.get(key, 0.0) * persona[key] for key in RUBRIC_KEYS)


def _lowest_persona(personas: list[dict], weights) -> dict | None:
    if not personas:
        return None
    return min(personas, key=lambda p: _persona_composite(p, weights))


def _score_breakdown_body(final_state: dict, weights) -> str:
    report = build_score_report(final_state)
    personas = report.get("personas", [])
    lowest = _lowest_persona(personas, weights)

    lines = [f"- Aggregate: {report.get('aggregate_score')}"]
    for persona in personas:
        lines.append(
            f"- {persona['persona']}: keyword_match={persona['keyword_match']}, "
            f"impact_quality={persona['impact_quality']}, coherence={persona['coherence']}, "
            f"plausibility={persona['plausibility']}, formatting={persona['formatting']}"
        )
    if lowest is not None:
        lines.append(f"- Lowest persona: {lowest['persona']}")
    return "\n".join(lines)


def _find_existing_note(runs_dir: Path, job_id: str) -> Path | None:
    if not runs_dir.is_dir():
        return None
    for path in sorted(runs_dir.glob("*.md")):
        if read_note(path).frontmatter.get("job_id") == job_id:
            return path
    return None


def _derived_jd_type(role: str | None, domains: list[str]) -> list[str]:
    """Human/Dataview display value: ``[role, *domains]`` (deduped, defensively)."""
    tags = [role] if role else []
    for domain in domains:
        if domain not in tags:
            tags.append(domain)
    return tags


def write_run_note(
    job: Any,
    final_state: dict,
    role: str | None,
    domains: list[str],
    *,
    settings: VaultSettings,
) -> Path | None:
    """Write (or overwrite) the run note for *job*. No-op when disabled."""
    if not settings.enabled or settings.dir is None:
        return None

    runs_dir = settings.dir / "runs"
    existing_path = _find_existing_note(runs_dir, job.job_id)

    outcome, outcome_date = "pending", ""
    if existing_path is not None:
        existing_fm = read_note(existing_path).frontmatter
        outcome = existing_fm.get("outcome", outcome)
        outcome_date = existing_fm.get("outcome_date", outcome_date)

    created = datetime.now(timezone.utc)
    path = existing_path or runs_dir / f"{created.date().isoformat()}-{_slugify(job.label)}.md"

    tuning = get_tuning(final_state)
    frontmatter_data = {
        "job_id": job.job_id,
        "label": job.label,
        "jd_name": job.jd_name,
        "role": role,
        "domains": list(domains),
        "jd_type": _derived_jd_type(role, domains),
        "created": created.isoformat(),
        "internal_score": final_state.get("aggregate_score"),
        "passed": bool(final_state.get("passed", False)),
        "threshold_used": tuning.threshold,
        "rubric_weights_used": dict(tuning.rubric_weights),
        "bullet_shapes_used": job.bullet_shapes,
        "learning_used": bool(getattr(job, "obsidian_learn", False)),
        "outcome": outcome,
        "outcome_date": outcome_date,
    }

    bullets_section = "\n".join(f"- {b}" for b in _final_bullets(final_state)) or "(none)"
    body = (
        "## Final bullets\n"
        f"{bullets_section}\n\n"
        "## Score breakdown\n"
        f"{_score_breakdown_body(final_state, tuning.rubric_weights)}\n"
    )

    write_note(path, frontmatter_data, body)
    return path
