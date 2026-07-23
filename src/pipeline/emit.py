"""Emit node — write the winning draft and its score report to ``out/``.

Writes three deliverables into the output directory:

- ``resume_optimized.pdf`` — a copy of the winning ``pdf_path``. On a hard
  compile failure there may be no pdf; the report is still written.
- ``score_report.json`` — per-persona rubric breakdowns, the aggregate, the
  iteration count, best score, and whether the run passed or hit the cap (with a
  warning on cap-hit).
- A TRUE-GAPS section inside the report — the competencies the Gap Analyzer
  flagged ``no_evidence=True``, so the user sees what the resume genuinely
  cannot claim.

Pure I/O: no LLM, no network. The node reads state and writes files; it returns
a NEW dict with the paths it wrote (never mutates input state).
"""
import json
import shutil
from pathlib import Path

from src.pipeline.schemas import PanelScore, ReframingTarget

_PDF_NAME = "resume_optimized.pdf"
_REPORT_NAME = "score_report.json"

_CAP_HIT_WARNING = (
    "Iteration cap reached without clearing the score threshold. Emitting the "
    "BEST-scoring draft seen across all iterations, not the last. Review the "
    "true-gaps section — the target role may require competencies the resume "
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
    """Competencies flagged ``no_evidence`` — what the resume can't claim."""
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


def _copy_pdf(pdf_path: str, out_path: Path) -> str | None:
    """Copy the winning pdf into ``out_path``; return its path or None."""
    if not pdf_path:
        return None
    src = Path(pdf_path)
    if not src.is_file():
        return None
    shutil.copyfile(src, out_path)
    return str(out_path)


def emit(state: dict, out_dir: str = "out") -> dict:
    """Node: write the winning pdf + score report to ``out_dir``.

    Args:
        state: The final pipeline state.
        out_dir: Destination directory (created if absent).

    Returns:
        A NEW dict with ``output_pdf`` (str | None) and ``output_report`` (str).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = build_score_report(state)
    report_path = out / _REPORT_NAME
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_pdf = _copy_pdf(state.get("pdf_path", ""), out / _PDF_NAME)

    return {"output_pdf": output_pdf, "output_report": str(report_path)}


def emit_node(state: dict) -> dict:
    """Graph-node wrapper: emit to the ``out_dir`` carried on the state.

    The CLI seeds ``out_dir`` into the initial state; defaults to ``out/``.
    Adds ``emitted=True`` as the terminal completion signal.
    """
    result = emit(state, out_dir=state.get("out_dir", "out"))
    return {**result, "emitted": True}
