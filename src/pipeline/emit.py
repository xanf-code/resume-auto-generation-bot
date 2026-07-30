"""Emit node - write the winning draft's deliverables to a per-JD package folder.

For a JD file ``JD1.txt`` the pipeline writes ``out/JD1/`` containing:

- ``resume.pdf`` - a copy of the winning ``pdf_path``. On a hard compile failure
  there may be no pdf; the rest of the package is still written.
- ``score_report.json`` - per-persona rubric breakdowns, the aggregate, the
  iteration count, best score, and whether the run passed or hit the cap (with a
  warning on cap-hit). Includes a TRUE-GAPS section - the competencies the Gap
  Analyzer flagged ``no_evidence=True`` - so the user sees what the resume
  genuinely cannot claim.
- ``skills.json`` - the writer's optimized, JD-tailored skill list as four
  machine-readable buckets. Skills are NOT rendered into the resume LaTeX; this
  file is the sole skills deliverable, consumed both by the CLI and by the web
  layer's ``GET /jobs/{id}/skills`` endpoint (the frontend renders the buckets
  from this).

When ``jd_name`` is absent the package collapses to ``out_dir`` itself and the
PDF keeps the legacy ``resume_optimized.pdf`` name.

Pure I/O: no LLM, no network. The node reads state and writes files; it returns
a NEW dict with the paths it wrote (never mutates input state).
"""
import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

from src.pipeline.schemas import PanelScore, ReframingTarget, SkillDump

_PDF_NAME_DEFAULT = "resume_optimized.pdf"
_PDF_NAME_PACKAGE = "resume.pdf"
_REPORT_NAME = "score_report.json"
_SKILLS_NAME = "skills.json"

_CAP_HIT_WARNING = (
    "Iteration cap reached without clearing the score threshold. Emitting the "
    "BEST-scoring draft seen across all iterations, not the last. Review the "
    "true-gaps section - the target role may require competencies the resume "
    "cannot honestly claim."
)


def _persona_breakdown(score: PanelScore) -> dict:
    """One persona's rubric dimensions as a plain JSON-serialisable dict."""
    return {
        "persona": score.persona,
        "keyword_match": score.keyword_match,
        "impact_quality": score.impact_quality,
        "coherence": score.coherence,
        "plausibility": score.plausibility,
        "formatting": score.formatting,
        "notes": score.notes,
    }


def _true_gaps(gap_targets: list[ReframingTarget]) -> list[dict]:
    """Competencies flagged ``no_evidence`` - what the resume can't claim."""
    return [
        {"competency": t.competency, "weight": t.weight}
        for t in gap_targets
        if t.no_evidence
    ]


def build_score_report(state: dict) -> dict:
    """Assemble the score-report payload from the final pipeline state (pure)."""
    panel_scores = state.get("panel_scores", []) or []
    gap_targets = state.get("gap_targets", []) or []
    cap_hit = bool(state.get("cap_hit", False))

    report = {
        "passed": bool(state.get("passed", False)),
        "cap_hit": cap_hit,
        "aggregate_score": state.get("aggregate_score"),
        "best_score": state.get("best_score"),
        "iteration": state.get("iteration"),
        "personas": [_persona_breakdown(s) for s in panel_scores],
        "true_gaps": _true_gaps(gap_targets),
    }
    if cap_hit:
        report["warning"] = _CAP_HIT_WARNING
    return report


def _skills_from_state(state: dict) -> SkillDump:
    """Resolve the skill dump: generated once by generate_skills, stable across iterations."""
    dump = state.get("skill_dump")
    return dump if isinstance(dump, SkillDump) else SkillDump()


def _copy_pdf(pdf_path: str, out_path: Path) -> str | None:
    """Copy the winning pdf into ``out_path``; return its path or None."""
    if not pdf_path:
        return None
    src = Path(pdf_path)
    if not src.is_file():
        return None
    shutil.copyfile(src, out_path)
    return str(out_path)


def emit(state: dict, out_dir: str = "out", write_files: bool = True) -> dict:
    """Node: write the winning draft's package to ``out_dir/{jd_name}/``.

    Args:
        state: The final pipeline state.
        out_dir: Root output directory (created if absent). Only touched on the
            CLI path; ignored entirely when ``write_files`` is False.
        write_files: When True (CLI) write the full per-JD package to disk — the
            PDF copy, score_report.json, and skills.json. When False (web runner)
            write NOTHING locally: Supabase is the only sink. ``output_pdf`` then
            passes through the compiler's own temp PDF path so the caller can
            upload it directly; the JSON artifacts persist to the repository.

    Returns:
        A NEW dict with ``output_pdf`` (str | None), ``output_report`` (str | None),
        and ``output_skills`` (str | None) — paths written, or None when skipped.
    """
    # Prefer the best-scoring PDF over the last-compiled PDF.
    # Fallback chain: best_pdf_path → pdf_path → None (no PDF).
    effective_pdf_path = state.get("best_pdf_path") or state.get("pdf_path", "")

    # Web path: never create a local out/ tree. Hand back the compiled PDF's own
    # (temp) path so the caller uploads it straight to Storage — Supabase is the
    # only sink; the JSON artifacts persist to the repository, not disk.
    if not write_files:
        return {
            "output_pdf": effective_pdf_path or None,
            "output_report": None,
            "output_skills": None,
        }

    jd_name = state.get("jd_name", "").strip()
    # Package the run into a per-JD folder so outputs never collide across JDs.
    # Without a jd_name, collapse to out_dir and keep the legacy PDF name.
    pkg_dir = Path(out_dir) / jd_name if jd_name else Path(out_dir)
    pdf_filename = _PDF_NAME_PACKAGE if jd_name else _PDF_NAME_DEFAULT
    pkg_dir.mkdir(parents=True, exist_ok=True)

    report = build_score_report(state)
    report_path = pkg_dir / _REPORT_NAME
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Four skill buckets as JSON - the sole skills deliverable, parsed by the
    # CLI and by GET /jobs/{id}/skills into a DTO the frontend renders.
    skills = _skills_from_state(state)
    skills_path = pkg_dir / _SKILLS_NAME
    skills_path.write_text(
        json.dumps(skills.model_dump(), indent=2), encoding="utf-8"
    )

    output_pdf = _copy_pdf(effective_pdf_path, pkg_dir / pdf_filename)

    return {
        "output_pdf": output_pdf,
        "output_report": str(report_path),
        "output_skills": str(skills_path),
    }


def emit_node(state: dict) -> dict:
    """Graph-node wrapper: emit to the ``out_dir`` carried on the state."""
    out_dir = state.get("out_dir", "out")
    write_files = state.get("emit_write_files", True)
    if write_files:
        log.info("emit         | writing package → %s/", out_dir)
    else:
        log.info("emit         | no local writes (Supabase-only); passing PDF through for upload")
    result = emit(state, out_dir=out_dir, write_files=write_files)
    log.info("emit         | PDF    → %s", result.get("output_pdf") or "(none - compile never succeeded)")
    log.info("emit         | report → %s", result.get("output_report") or "(skipped)")
    log.info("emit         | skills → %s", result.get("output_skills") or "(skipped)")
    return {**result, "emitted": True}
