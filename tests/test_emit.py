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


# --- best_pdf_path fallback chain (Gap 2 fix) ----------------------------------


def test_emit_uses_best_pdf_path_when_available(tmp_path):
    """best_pdf_path is used when pdf_path is empty (compile-exhaustion case)."""
    best_pdf = tmp_path / "best.pdf"
    best_pdf.write_bytes(b"%PDF best")
    out_dir = tmp_path / "out"

    state = _make_state(tmp_path, passed=False, hit_cap=True)
    state["pdf_path"] = ""
    state["best_pdf_path"] = str(best_pdf)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    out_pdf = out_dir / "resume_optimized.pdf"
    assert out_pdf.is_file()
    assert out_pdf.read_bytes() == b"%PDF best"
    assert result.get("output_pdf") == str(out_pdf)


def test_emit_uses_best_pdf_path_over_pdf_path_when_both_present(tmp_path):
    """best_pdf_path wins over pdf_path when both are present."""
    best_pdf = tmp_path / "best.pdf"
    last_pdf = tmp_path / "last.pdf"
    best_pdf.write_bytes(b"%PDF best")
    last_pdf.write_bytes(b"%PDF last")
    out_dir = tmp_path / "out"

    state = _make_state(tmp_path)
    state["pdf_path"] = str(last_pdf)
    state["best_pdf_path"] = str(best_pdf)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert (out_dir / "resume_optimized.pdf").read_bytes() == b"%PDF best"


def test_emit_falls_back_to_pdf_path(tmp_path):
    """When best_pdf_path is absent, pdf_path is used as fallback."""
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    # state has pdf_path pointing to a real file; best_pdf_path not set
    state.pop("best_pdf_path", None)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert (out_dir / "resume_optimized.pdf").is_file()
    assert result.get("output_pdf") is not None


def test_emit_falls_back_gracefully_when_both_absent(tmp_path):
    """No PDF in state → no crash, output_pdf is None, report still written."""
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path, passed=False)
    state["pdf_path"] = ""
    state.pop("best_pdf_path", None)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert (out_dir / "score_report.json").is_file()
    assert result.get("output_pdf") is None


# --- JD-derived output filename -----------------------------------------------


def test_emit_uses_jd_name_for_pdf_filename(tmp_path):
    """When jd_name is in state, the output PDF uses that stem."""
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    state["jd_name"] = "amazon_sde"

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert result["output_pdf"].endswith("amazon_sde.pdf")
    assert (out_dir / "amazon_sde.pdf").is_file()


def test_emit_falls_back_to_resume_optimized_when_no_jd_name(tmp_path):
    """When jd_name is absent, the output PDF falls back to resume_optimized.pdf."""
    out_dir = tmp_path / "out"
    state = _make_state(tmp_path)
    state.pop("jd_name", None)

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert result["output_pdf"].endswith("resume_optimized.pdf")
    assert (out_dir / "resume_optimized.pdf").is_file()


def test_emit_jd_name_used_for_best_pdf_path_too(tmp_path):
    """jd_name controls the output filename regardless of which pdf_path source wins."""
    best_pdf = tmp_path / "best.pdf"
    best_pdf.write_bytes(b"%PDF best")
    out_dir = tmp_path / "out"

    state = _make_state(tmp_path, passed=False, hit_cap=True)
    state["pdf_path"] = ""
    state["best_pdf_path"] = str(best_pdf)
    state["jd_name"] = "google_l5"

    result = emit_mod.emit(state, out_dir=str(out_dir))

    assert result["output_pdf"].endswith("google_l5.pdf")
    assert (out_dir / "google_l5.pdf").read_bytes() == b"%PDF best"
