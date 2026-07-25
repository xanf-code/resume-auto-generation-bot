"""Tests for ResumeRepository - uses a fully mocked Supabase client."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from src.db.models import JobRecord
from src.db.repository import ResumeRepository
from src.db.config import DbSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings() -> DbSettings:
    return DbSettings(url="https://example.supabase.co", service_key="fake-key")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(**overrides) -> JobRecord:
    defaults = dict(
        job_id="test-job-id-1",
        label="Test",
        status="queued",
        created_at=_now(),
    )
    defaults.update(overrides)
    return JobRecord(**defaults)


def _make_repo(client=None) -> tuple[ResumeRepository, MagicMock]:
    """Return (repo, mock_client)."""
    if client is None:
        client = MagicMock()
    settings = _settings()
    repo = ResumeRepository(client=client, settings=settings)
    return repo, client


def _mock_table(client: MagicMock) -> MagicMock:
    """Return the table mock so we can assert on chained calls."""
    return client.table.return_value


# ---------------------------------------------------------------------------
# Test: create() inserts a row
# ---------------------------------------------------------------------------

def test_create_calls_insert():
    repo, client = _make_repo()
    rec = _make_record()
    table = _mock_table(client)
    table.insert.return_value.execute.return_value = MagicMock(data=[{}])

    repo.create(rec)

    client.table.assert_called_with(ResumeRepository.TABLE)
    table.insert.assert_called_once()
    inserted_data = table.insert.call_args[0][0]
    assert inserted_data["job_id"] == rec.job_id
    assert inserted_data["label"] == rec.label
    assert inserted_data["status"] == rec.status


# ---------------------------------------------------------------------------
# Test: get() returns JobRecord when found
# ---------------------------------------------------------------------------

def test_get_returns_record_when_found():
    repo, client = _make_repo()
    table = _mock_table(client)

    dt_str = _now().isoformat()
    row = {
        "job_id": "test-job-id-1",
        "label": "Test",
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
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[row])

    result = repo.get("test-job-id-1")

    assert result is not None
    assert isinstance(result, JobRecord)
    assert result.job_id == "test-job-id-1"
    assert result.label == "Test"


def test_get_returns_none_when_not_found():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    result = repo.get("nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# Test: list() returns ordered list
# ---------------------------------------------------------------------------

def test_list_returns_list_ordered_by_created_at():
    repo, client = _make_repo()
    table = _mock_table(client)

    dt_str = _now().isoformat()
    rows = [
        {
            "job_id": f"job-{i}",
            "label": f"Job {i}",
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
        for i in range(3)
    ]
    table.select.return_value.order.return_value.execute.return_value = MagicMock(data=rows)

    result = repo.list()

    assert len(result) == 3
    assert all(isinstance(r, JobRecord) for r in result)
    # Verify order call
    table.select.return_value.order.assert_called_once()


# ---------------------------------------------------------------------------
# Test: set_status() calls update + eq
# ---------------------------------------------------------------------------

def test_set_status_calls_update_with_status():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    repo.set_status("job-1", "running")

    table.update.assert_called_once()
    update_data = table.update.call_args[0][0]
    assert update_data["status"] == "running"
    table.update.return_value.eq.assert_called_with("job_id", "job-1")


def test_set_status_with_started_at():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    dt = _now()
    repo.set_status("job-1", "running", started_at=dt)

    update_data = table.update.call_args[0][0]
    assert "started_at" in update_data
    assert update_data["status"] == "running"


# ---------------------------------------------------------------------------
# Test: save_artifacts() calls update with all artifact fields
# ---------------------------------------------------------------------------

def test_save_artifacts_updates_correct_fields():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    repo.save_artifacts(
        "job-1",
        best_latex="\\documentclass{article}",
        output_skills={"language_and_framework": ["Python"]},
        score_report={"passed": True, "aggregate_score": 85.0},
        aggregate_score=85.0,
        passed=True,
        pdf_object_key="job-1/resume.pdf",
    )

    table.update.assert_called_once()
    update_data = table.update.call_args[0][0]
    assert update_data["best_latex"] == "\\documentclass{article}"
    assert update_data["output_skills"] == {"language_and_framework": ["Python"]}
    assert update_data["score_report"] == {"passed": True, "aggregate_score": 85.0}
    assert update_data["aggregate_score"] == 85.0
    assert update_data["passed"] is True
    assert update_data["pdf_object_key"] == "job-1/resume.pdf"
    table.update.return_value.eq.assert_called_with("job_id", "job-1")


# ---------------------------------------------------------------------------
# Test: rename() updates label and returns updated record
# ---------------------------------------------------------------------------

def test_rename_calls_update_and_returns_record():
    repo, client = _make_repo()
    table = _mock_table(client)

    dt_str = _now().isoformat()
    updated_row = {
        "job_id": "job-1",
        "label": "New Label",
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
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_row])

    result = repo.rename("job-1", "New Label")

    assert result is not None
    assert isinstance(result, JobRecord)
    assert result.label == "New Label"
    update_data = table.update.call_args[0][0]
    assert update_data["label"] == "New Label"


def test_rename_returns_none_when_not_found():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    result = repo.rename("nonexistent", "New Label")

    assert result is None


# ---------------------------------------------------------------------------
# Test: delete() calls delete().eq()
# ---------------------------------------------------------------------------

def test_delete_calls_delete_eq():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"job_id": "job-1"}])

    result = repo.delete("job-1")

    assert result is True
    table.delete.return_value.eq.assert_called_with("job_id", "job-1")


def test_delete_returns_false_when_nothing_deleted():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    result = repo.delete("nonexistent")

    assert result is False


# ---------------------------------------------------------------------------
# Test: mark_interrupted_running() updates stale rows and returns count
# ---------------------------------------------------------------------------

def test_mark_interrupted_running_updates_queued_and_running():
    repo, client = _make_repo()
    table = _mock_table(client)
    # Simulate 2 stale rows updated
    affected_rows = [{"job_id": "j1"}, {"job_id": "j2"}]
    table.update.return_value.in_.return_value.execute.return_value = MagicMock(data=affected_rows)

    count = repo.mark_interrupted_running()

    assert count == 2
    table.update.assert_called_once()
    update_data = table.update.call_args[0][0]
    assert update_data["status"] == "failed"
    assert "error" in update_data
    assert "finished_at" in update_data
    # Verify it filters on the correct statuses
    table.update.return_value.in_.assert_called_with("status", ["queued", "running"])
