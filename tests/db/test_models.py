"""Tests for JobRecord dataclass and row conversion helpers."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db.models import JobRecord, record_to_row, row_to_record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _minimal_record(**overrides) -> JobRecord:
    defaults = dict(
        job_id="00000000-0000-0000-0000-000000000001",
        label="Test Job",
        status="queued",
        created_at=_now(),
    )
    defaults.update(overrides)
    return JobRecord(**defaults)


# ---------------------------------------------------------------------------
# Test 1: JobRecord is a frozen dataclass with expected fields
# ---------------------------------------------------------------------------

def test_job_record_has_expected_fields():
    rec = _minimal_record()
    assert rec.job_id == "00000000-0000-0000-0000-000000000001"
    assert rec.label == "Test Job"
    assert rec.status == "queued"
    assert isinstance(rec.created_at, datetime)
    assert rec.started_at is None
    assert rec.finished_at is None
    assert rec.error is None
    assert rec.user_id is None
    assert rec.best_latex is None
    assert rec.output_skills is None
    assert rec.score_report is None
    assert rec.aggregate_score is None
    assert rec.passed is None
    assert rec.pdf_object_key is None


def test_job_record_is_frozen():
    """Frozen dataclass should raise AttributeError on mutation attempt."""
    rec = _minimal_record()
    with pytest.raises((AttributeError, TypeError)):
        rec.label = "mutated"  # type: ignore[misc]


def test_job_record_defaults():
    rec = _minimal_record()
    assert rec.resume_tex_raw == ""
    assert rec.jd_raw == ""
    assert rec.jd_name == ""
    assert rec.enable_scoring is False
    assert rec.tuning is None
    assert rec.models is None
    assert rec.bullet_shapes is None


# ---------------------------------------------------------------------------
# Test 2: record_to_row converts datetimes to ISO strings
# ---------------------------------------------------------------------------

def test_record_to_row_converts_datetimes():
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    rec = _minimal_record(created_at=dt)
    row = record_to_row(rec)
    assert isinstance(row["created_at"], str)
    assert "2024-01-15" in row["created_at"]


def test_record_to_row_none_datetimes_stay_none():
    rec = _minimal_record()
    row = record_to_row(rec)
    assert row["started_at"] is None
    assert row["finished_at"] is None


def test_record_to_row_includes_all_fields():
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    rec = _minimal_record(
        created_at=dt,
        label="My Job",
        status="running",
        enable_scoring=True,
        resume_tex_raw="\\documentclass",
        jd_raw="some jd",
        jd_name="Acme",
    )
    row = record_to_row(rec)
    assert row["job_id"] == rec.job_id
    assert row["label"] == "My Job"
    assert row["status"] == "running"
    assert row["enable_scoring"] is True
    assert row["resume_tex_raw"] == "\\documentclass"
    assert row["jd_raw"] == "some jd"
    assert row["jd_name"] == "Acme"


# ---------------------------------------------------------------------------
# Test 3: row_to_record parses ISO datetime strings back to datetimes
# ---------------------------------------------------------------------------

def test_row_to_record_parses_datetime_strings():
    dt_str = "2024-01-15T10:30:00+00:00"
    row = {
        "job_id": "abc-123",
        "label": "Test",
        "status": "done",
        "created_at": dt_str,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "user_id": None,
        "resume_tex_raw": "",
        "jd_raw": "",
        "jd_name": "",
        "enable_scoring": False,
        "tuning": None,
        "models": None,
        "bullet_shapes": None,
        "best_latex": None,
        "output_skills": None,
        "score_report": None,
        "aggregate_score": None,
        "passed": None,
        "pdf_object_key": None,
    }
    rec = row_to_record(row)
    assert isinstance(rec.created_at, datetime)
    assert rec.created_at.year == 2024
    assert rec.created_at.month == 1
    assert rec.started_at is None


def test_row_to_record_handles_null_artifacts():
    dt_str = "2024-02-01T00:00:00+00:00"
    row = {
        "job_id": "xyz",
        "label": "Null artifacts",
        "status": "queued",
        "created_at": dt_str,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "user_id": None,
        "resume_tex_raw": "",
        "jd_raw": "",
        "jd_name": "",
        "enable_scoring": False,
        "tuning": None,
        "models": None,
        "bullet_shapes": None,
        "best_latex": None,
        "output_skills": None,
        "score_report": None,
        "aggregate_score": None,
        "passed": None,
        "pdf_object_key": None,
    }
    rec = row_to_record(row)
    assert rec.best_latex is None
    assert rec.output_skills is None
    assert rec.score_report is None
    assert rec.pdf_object_key is None


# ---------------------------------------------------------------------------
# Test 4: Round-trip record → row → record preserves fields
# ---------------------------------------------------------------------------

def test_round_trip_preserves_all_fields():
    dt = datetime(2024, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    started = datetime(2024, 3, 10, 12, 1, 0, tzinfo=timezone.utc)
    finished = datetime(2024, 3, 10, 12, 5, 0, tzinfo=timezone.utc)

    original = JobRecord(
        job_id="round-trip-id",
        label="Round Trip",
        status="done",
        created_at=dt,
        started_at=started,
        finished_at=finished,
        error=None,
        user_id=None,
        resume_tex_raw="\\documentclass{article}",
        jd_raw="Senior engineer",
        jd_name="Acme Corp",
        enable_scoring=True,
        tuning={"threshold": 75},
        models={"writer": "gpt-4"},
        bullet_shapes=["star"],
        best_latex="\\begin{document}best\\end{document}",
        output_skills={"language_and_framework": ["Python"]},
        score_report={"passed": True, "aggregate_score": 88.5},
        aggregate_score=88.5,
        passed=True,
        pdf_object_key="round-trip-id/resume.pdf",
    )

    row = record_to_row(original)
    recovered = row_to_record(row)

    assert recovered.job_id == original.job_id
    assert recovered.label == original.label
    assert recovered.status == original.status
    assert isinstance(recovered.created_at, datetime)
    assert isinstance(recovered.started_at, datetime)
    assert isinstance(recovered.finished_at, datetime)
    assert recovered.resume_tex_raw == original.resume_tex_raw
    assert recovered.jd_raw == original.jd_raw
    assert recovered.jd_name == original.jd_name
    assert recovered.enable_scoring == original.enable_scoring
    assert recovered.tuning == original.tuning
    assert recovered.best_latex == original.best_latex
    assert recovered.output_skills == original.output_skills
    assert recovered.score_report == original.score_report
    assert recovered.aggregate_score == original.aggregate_score
    assert recovered.passed == original.passed
    assert recovered.pdf_object_key == original.pdf_object_key
