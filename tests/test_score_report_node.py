"""Unit tests for src.pipeline.score_report — the score_report_node that runs after emit.

These tests verify:
1. score_report_node runs when a PDF exists
2. score_report_node skips when no PDF exists
3. The markdown report is written to disk

NO live LLM calls — generate_score_report is mocked.
"""
from unittest.mock import patch

from src.pipeline.score_report import score_report_node, format_markdown_report
from src.resume_scorer import (
    BonusPoints,
    CategoryScore,
    Deductions,
    ResumeScore,
    Scores,
    ScoringResult,
)


@patch("src.pipeline.score_report.generate_score_report")
def test_score_report_node_runs_when_pdf_exists(mock_generate):
    """score_report_node calls generate_score_report when PDF exists."""
    mock_generate.return_value = "/tmp/resume_score_report.md"

    state = {"output_pdf": "/tmp/resume.pdf", "out_dir": "/tmp"}
    result = score_report_node(state)

    # Verify generate_score_report was called
    mock_generate.assert_called_once_with("/tmp/resume.pdf", "/tmp")

    # Verify result contains the report path
    assert result["score_report_md"] == "/tmp/resume_score_report.md"


def test_score_report_node_skips_when_no_pdf():
    """score_report_node skips scoring when output_pdf is None."""
    state = {"output_pdf": None}
    result = score_report_node(state)

    assert result["score_report_md"] is None


@patch("src.pipeline.score_report.generate_score_report")
def test_score_report_node_handles_errors_gracefully(mock_generate):
    """score_report_node returns None if generate_score_report fails."""
    mock_generate.side_effect = RuntimeError("Scoring failed")

    state = {"output_pdf": "/tmp/resume.pdf", "out_dir": "/tmp"}
    result = score_report_node(state)

    # Should not crash, just return None
    assert result["score_report_md"] is None


def test_format_markdown_report():
    """format_markdown_report generates well-formatted markdown."""
    result = ScoringResult(
        raw_score=ResumeScore(
            scores=Scores(
                self_projects=CategoryScore(score=30, max=35, evidence="5 projects"),
                production=CategoryScore(score=38, max=40, evidence="3 YOE"),
                technical_skills=CategoryScore(score=14, max=15, evidence="10 langs"),
                resume_visual_aesthetics=CategoryScore(score=9, max=10, evidence="Clean"),
            ),
            bonus_points=BonusPoints(total=15, breakdown="Founder +10, Blog +5"),
            deductions=Deductions(total=2, reasons="Missing link -2"),
            key_strengths=["Strong backend", "Good docs", "Open source"],
            areas_for_improvement=["Add testing", "Live demos"],
        ),
        category_total=91,
        final_score=104,
    )

    md = format_markdown_report(result)

    # Check that all key sections are present
    assert "**Final Score** | **104/120**" in md
    assert "30/35" in md  # Self Projects
    assert "38/40" in md  # Production
    assert "14/15" in md  # Technical Skills
    assert "9/10" in md   # Resume Visual Aesthetics
    assert "Founder +10, Blog +5" in md
    assert "Missing link -2" in md
    assert "Strong backend" in md
    assert "Add testing" in md
