"""Shared pytest configuration for web route tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.agents.jd_tagger import JdClassification


def pytest_configure(config):
    """Register custom marks so -m integration works cleanly."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require external tools like tectonic)",
    )


@pytest.fixture(autouse=True)
def _no_real_jd_tagging(monkeypatch):
    """Never let a test hit the real jd_tagger LLM call.

    ``run_job`` always classifies the JD into a role/domains split (Phase 9/10
    wiring), so any test that drives a job through the manager now reaches
    ``src.web.runner.classify_jd_type`` and accesses ``.role``/``.domains``/
    ``.combined_tags`` on its return value. Default it to a neutral
    classification here; tests that care about specific role/domains override
    it locally within their own scope.
    """
    monkeypatch.setattr(
        "src.web.runner.classify_jd_type",
        lambda jd_raw: JdClassification(role=None, domains=[]),
    )


def seed_job_done(manager, job_id: str, **artifacts) -> None:
    """Persist a done status + artifacts via the repository (SSOT)."""
    repo = manager._repo
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
        status="done",
        finished_at=datetime.now(timezone.utc),
    )
