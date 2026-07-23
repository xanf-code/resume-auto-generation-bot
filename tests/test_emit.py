"""Tests for src.pipeline.emit — output writer. NO LLM, NO network.

Uses a temp out dir and a fake state (fake pdf file, panel_scores, gap_targets
including a no_evidence target). Asserts:

- ``score_report.json`` is written with per-persona breakdown + aggregate;
- the true-gaps list includes the no_evidence competency (and excludes sourced
  competencies);
- the winning pdf is copied to ``resume_optimized.pdf``.
"""
import json

from src.pipeline import emit as emit_mod
from src.pipeline.schemas import PanelScore, ReframingTarget


def _panel_scores() -> list[PanelScore]:
    return [
        PanelScore(persona="ATS Matcher", keyword_match=90, impact_quality=88,
                   coherence=85, plausibility=90, formatting=92, notes="ok"),
        PanelScore(persona="Hiring Manager", keyword_match=85, impact_quality=90,
                   coherence=88, plausibility=87, formatting=90, notes="ok"),
        PanelScore(persona="Technical Screener", keyword_match=80, impact_quality=82,
                   coherence=84, plausibility=88, formatting=86, notes="ok"),
        PanelScore(persona="Skeptic", keyword_match=78, impact_quality=80,
                   coherence=82, plausibility=84, formatting=85, notes="ok"),
    ]


def _gap_targets() -> list[ReframingTarget]:
    return [
        ReframingTarget(
            competency="Salesforce",
            weight=0.9,
            host_role_index=0,
            real_evidence=["Built CRM-sync ETL job."],
            framing_guidance="Frame as REST-based CRM integration.",
            no_evidence=False,
        ),
        ReframingTarget(
            competency="Kubernetes",
            weight=0.6,
            host_role_index=0,
            real_evidence=[],
            framing_guidance="",
            no_evidence=True,
        ),
    ]


def _make_state(tmp_path, *, passed=True, hit_cap=False) -> dict:
    pdf = tmp_path / "winner.pdf"
    pdf.write_bytes(b"%PDF-1.5 fake pdf bytes")
    return {
        "pdf_path": str(pdf),
        "best_latex": "\\documentclass{article}",
        "panel_scores": _panel_scores(),
        "aggregate_score": 88.5,
        "passed": passed,
        "gap_targets": _gap_targets(),
        "iteration": 3,
        "best_score": 88.5,
        "cap_hit": hit_cap,
    }


def test_emit_writes_pdf_and_report(tmp_path):
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    pdf_out = out_dir / "resume_optimized.pdf"
    report_out = out_dir / "score_report.json"
    assert pdf_out.is_file()
    assert pdf_out.read_bytes() == b"%PDF-1.5 fake pdf bytes"
    assert report_out.is_file()

    # The node returns paths it wrote.
    assert result.get("output_pdf") == str(pdf_out)
    assert result.get("output_report") == str(report_out)


def test_score_report_has_per_persona_and_aggregate(tmp_path):
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    emit_mod.emit(state, out_dir=str(out_dir))

    report = json.loads((out_dir / "score_report.json").read_text())

    assert report["aggregate_score"] == 88.5
    assert report["passed"] is True
    personas = {p["persona"] for p in report["personas"]}
    assert personas == {"ATS Matcher", "Hiring Manager", "Technical Screener", "Skeptic"}
    # Each persona breakdown carries all five rubric dimensions.
    ats = next(p for p in report["personas"] if p["persona"] == "ATS Matcher")
    for dim in ("keyword_match", "impact_quality", "coherence", "plausibility", "formatting"):
        assert dim in ats


def test_true_gaps_lists_only_no_evidence_competencies(tmp_path):
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    emit_mod.emit(state, out_dir=str(out_dir))

    report = json.loads((out_dir / "score_report.json").read_text())
    true_gaps = report["true_gaps"]
    competencies = {g["competency"] for g in true_gaps}

    assert "Kubernetes" in competencies, "no_evidence competency must appear"
    assert "Salesforce" not in competencies, "sourced competency must NOT appear"


def test_report_records_cap_hit_warning(tmp_path):
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path, passed=False, hit_cap=True)
    emit_mod.emit(state, out_dir=str(out_dir))

    report = json.loads((out_dir / "score_report.json").read_text())
    assert report["passed"] is False
    assert report["cap_hit"] is True
    assert report.get("warning"), "a cap-hit emit must carry a warning string"


def test_report_has_iteration_history_and_best_score(tmp_path):
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    emit_mod.emit(state, out_dir=str(out_dir))

    report = json.loads((out_dir / "score_report.json").read_text())
    assert report["iteration"] == 3
    assert report["best_score"] == 88.5


def test_emit_handles_missing_pdf_gracefully(tmp_path):
    """A hard-fail emit (no pdf_path) still writes a report, no crash."""
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path, passed=False, hit_cap=False)
    state["pdf_path"] = ""  # compile never produced a pdf

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert (out_dir / "score_report.json").is_file()
    assert result.get("output_pdf") is None
