"""Unit tests for src.resume_scorer — structured LLM-based resume scoring.

These tests verify:
1. ScoringResult.to_dict() serialization
2. score_resume() orchestration (mocked LLM)
3. main() CLI entry point (mocked subprocess + LLM)

NO live LLM calls — all LLM behaviour is mocked.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.resume_scorer import (
    BonusPoints,
    CategoryScore,
    Deductions,
    ResumeScore,
    Scores,
    ScoringResult,
    main,
    score_resume,
)


# --- ScoringResult.to_dict() --------------------------------------------------


def test_scoring_result_to_dict_structure():
    """to_dict() returns all required fields in the correct structure."""
    raw = ResumeScore(
        scores=Scores(
            self_projects=CategoryScore(score=25, max=35, evidence="5 solid projects"),
            production=CategoryScore(score=30, max=40, evidence="3 YOE at startups"),
            technical_skills=CategoryScore(score=12, max=15, evidence="10 languages"),
            resume_visual_aesthetics=CategoryScore(score=8, max=10, evidence="Clean layout"),
        ),
        bonus_points=BonusPoints(total=10, breakdown="Founder +8, Portfolio +2"),
        deductions=Deductions(total=3, reasons="Simple project -3"),
        key_strengths=["Strong backend", "Good docs"],
        areas_for_improvement=["Add testing", "Live demos"],
    )
    result = ScoringResult(raw_score=raw, category_total=75, final_score=82)
    d = result.to_dict()

    assert "category_scores" in d
    assert "bonus_points" in d
    assert "deductions" in d
    assert "category_total" in d
    assert "final_score" in d
    assert "key_strengths" in d
    assert "areas_for_improvement" in d

    # Check nested structure
    assert d["category_scores"]["self_projects"]["score"] == 25
    assert d["category_scores"]["production"]["score"] == 30
    assert d["bonus_points"]["total"] == 10
    assert d["deductions"]["total"] == 3
    assert d["category_total"] == 75
    assert d["final_score"] == 82


def test_scoring_result_to_dict_preserves_evidence():
    """to_dict() preserves evidence strings for each category."""
    raw = ResumeScore(
        scores=Scores(
            self_projects=CategoryScore(score=20, max=35, evidence="Evidence A"),
            production=CategoryScore(score=25, max=40, evidence="Evidence B"),
            technical_skills=CategoryScore(score=10, max=15, evidence="Evidence C"),
            resume_visual_aesthetics=CategoryScore(score=7, max=10, evidence="Evidence D"),
        ),
        bonus_points=BonusPoints(total=5, breakdown="Portfolio +5"),
        deductions=Deductions(total=0, reasons=""),
        key_strengths=["X"],
        areas_for_improvement=["Y"],
    )
    result = ScoringResult(raw_score=raw, category_total=62, final_score=67)
    d = result.to_dict()

    assert d["category_scores"]["self_projects"]["evidence"] == "Evidence A"
    assert d["category_scores"]["production"]["evidence"] == "Evidence B"
    assert d["category_scores"]["technical_skills"]["evidence"] == "Evidence C"
    assert d["category_scores"]["resume_visual_aesthetics"]["evidence"] == "Evidence D"


# --- score_resume() -----------------------------------------------------------


@patch("src.resume_scorer.parse_strong")
def test_score_resume_calls_llm_with_correct_prompts(mock_parse):
    """score_resume() calls parse_strong with system + criteria prompts."""
    mock_parse.return_value = ResumeScore(
        scores=Scores(
            self_projects=CategoryScore(score=30, max=35, evidence="E1"),
            production=CategoryScore(score=35, max=40, evidence="E2"),
            technical_skills=CategoryScore(score=13, max=15, evidence="E3"),
            resume_visual_aesthetics=CategoryScore(score=9, max=10, evidence="E4"),
        ),
        bonus_points=BonusPoints(total=15, breakdown="Founder +8, Blog +7"),
        deductions=Deductions(total=5, reasons="Simple project -5"),
        key_strengths=["Backend", "Docs"],
        areas_for_improvement=["Testing"],
    )

    result = score_resume("RESUME TEXT HERE")

    # Verify parse_strong was called
    mock_parse.assert_called_once()
    call_kwargs = mock_parse.call_args.kwargs
    assert "system" in call_kwargs
    assert "user" in call_kwargs
    assert "schema" in call_kwargs
    assert call_kwargs["schema"] == ResumeScore
    assert "RESUME TEXT HERE" in call_kwargs["user"]

    # Verify aggregation
    assert result.category_total == 30 + 35 + 13 + 9
    assert result.final_score == 87 + 15 - 5


@patch("src.resume_scorer.parse_strong")
def test_score_resume_enforces_120_cap(mock_parse):
    """score_resume() caps final_score at 120."""
    mock_parse.return_value = ResumeScore(
        scores=Scores(
            self_projects=CategoryScore(score=35, max=35, evidence="E1"),
            production=CategoryScore(score=40, max=40, evidence="E2"),
            technical_skills=CategoryScore(score=15, max=15, evidence="E3"),
            resume_visual_aesthetics=CategoryScore(score=10, max=10, evidence="E4"),
        ),
        bonus_points=BonusPoints(total=20, breakdown="Max bonus"),
        deductions=Deductions(total=0, reasons=""),
        key_strengths=["X"],
        areas_for_improvement=["Y"],
    )

    result = score_resume("PERFECT RESUME")

    # category_total = 35+40+15+10 = 100
    # final = 100 + 20 - 0 = 120 (should be capped)
    assert result.category_total == 100
    assert result.final_score == 120


@patch("src.resume_scorer.parse_strong")
def test_score_resume_handles_deductions_exceeding_score(mock_parse):
    """score_resume() allows negative final_score if deductions > score."""
    mock_parse.return_value = ResumeScore(
        scores=Scores(
            self_projects=CategoryScore(score=10, max=35, evidence="E1"),
            production=CategoryScore(score=5, max=40, evidence="E2"),
            technical_skills=CategoryScore(score=3, max=15, evidence="E3"),
            resume_visual_aesthetics=CategoryScore(score=2, max=10, evidence="E4"),
        ),
        bonus_points=BonusPoints(total=0, breakdown=""),
        deductions=Deductions(total=30, reasons="Multiple issues"),
        key_strengths=["None"],
        areas_for_improvement=["Everything"],
    )

    result = score_resume("WEAK RESUME")

    # category_total = 10+5+3+2 = 20
    # final = 20 + 0 - 30 = -10 (allowed, cap only applies upward)
    assert result.category_total == 20
    assert result.final_score == -10


# --- main() CLI entry point ---------------------------------------------------


@patch("subprocess.run")
@patch("src.resume_scorer.score_resume")
@patch("src.resume_scorer.require_api_key")
def test_main_extracts_pdf_and_scores(mock_require_key, mock_score, mock_subprocess, monkeypatch, capsys):
    """main() extracts PDF text via pdftotext and scores it."""
    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["scorer", "/tmp/resume.pdf"])

    # Mock PDF existence check
    with patch.object(Path, "exists", return_value=True):
        # Mock subprocess.run (pdftotext)
        mock_subprocess.return_value = MagicMock(stdout="EXTRACTED PDF TEXT")

        # Mock score_resume
        mock_score.return_value = ScoringResult(
            raw_score=ResumeScore(
                scores=Scores(
                    self_projects=CategoryScore(score=25, max=35, evidence="E1"),
                    production=CategoryScore(score=30, max=40, evidence="E2"),
                    technical_skills=CategoryScore(score=12, max=15, evidence="E3"),
                    resume_visual_aesthetics=CategoryScore(score=8, max=10, evidence="E4"),
                ),
                bonus_points=BonusPoints(total=10, breakdown="B"),
                deductions=Deductions(total=3, reasons="D"),
                key_strengths=["S"],
                areas_for_improvement=["I"],
            ),
            category_total=75,
            final_score=82,
        )

        main()

        # Verify pdftotext was called
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args.args[0]
        assert call_args[0] == "pdftotext"
        assert "/tmp/resume.pdf" in call_args[1]

        # Verify score_resume was called with extracted text
        mock_score.assert_called_once_with("EXTRACTED PDF TEXT")

        # Verify JSON output to stdout
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["final_score"] == 82
        assert output["category_total"] == 75

        # Verify summary to stderr
        assert "FINAL SCORE: 82/120" in captured.err


def test_main_fails_if_pdf_not_found(monkeypatch, capsys):
    """main() exits if PDF does not exist."""
    monkeypatch.setattr(sys, "argv", ["scorer", "/nonexistent.pdf"])

    with patch.object(Path, "exists", return_value=False):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "PDF not found" in captured.err


def test_main_fails_if_pdftotext_missing(monkeypatch, capsys):
    """main() exits if pdftotext is not installed."""
    monkeypatch.setattr(sys, "argv", ["scorer", "/tmp/resume.pdf"])

    with patch.object(Path, "exists", return_value=True):
        mock_run = MagicMock(side_effect=FileNotFoundError)
        with patch("subprocess.run", mock_run):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

            captured = capsys.readouterr()
            assert "pdftotext not found" in captured.err


@patch("subprocess.run")
@patch("src.resume_scorer.require_api_key")
def test_main_fails_if_api_key_missing(mock_require_key, mock_subprocess, monkeypatch, capsys):
    """main() exits if ANTHROPIC_API_KEY is not set."""
    monkeypatch.setattr(sys, "argv", ["scorer", "/tmp/resume.pdf"])
    mock_require_key.side_effect = RuntimeError("ANTHROPIC_API_KEY not set")

    with patch.object(Path, "exists", return_value=True):
        mock_subprocess.return_value = MagicMock(stdout="TEXT")

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "ANTHROPIC_API_KEY not set" in captured.err
