"""Shared pytest configuration for web route tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


def pytest_configure(config):
    """Register custom marks so -m integration works cleanly."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require external tools like tectonic)",
    )


def seed_job_done(manager, job_id: str, **artifacts) -> None:
    """Persist a done status + artifacts via the repository (SSOT)."""
    repo = manager._repo
    repo.set_status(job_id, "done", finished_at=datetime.now(timezone.utc))
    existing = repo.get(job_id)
    repo.save_artifacts(
        job_id,
        best_latex=artifacts.get("best_latex", existing.best_latex if existing else None),
        output_skills=artifacts.get(
            "output_skills", existing.output_skills if existing else None
        ),
        score_report=artifacts.get(
            "score_report", existing.score_report if existing else None
        ),
        aggregate_score=artifacts.get(
            "aggregate_score", existing.aggregate_score if existing else None
        ),
        passed=artifacts.get("passed", existing.passed if existing else None),
        pdf_object_key=artifacts.get(
            "pdf_object_key", existing.pdf_object_key if existing else None
        ),
    )
