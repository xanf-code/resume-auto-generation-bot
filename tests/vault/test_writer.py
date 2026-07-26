"""Tests for write_run_note - the end-of-run vault note writer."""
from __future__ import annotations

import pytest

from src.pipeline.schemas import RoleBullets, WriterOutput
from src.pipeline.tuning import PipelineTuning
from src.vault.config import VaultSettings
from src.vault.notes import read_note, write_note
from src.vault.writer import write_run_note
from src.web.job import Job


def _make_job(**overrides) -> Job:
    job = Job(label="Senior Engineer @ Acme", jd_name="acme-jd", bullet_shapes=["punchy"])
    for key, value in overrides.items():
        setattr(job, key, value)
    return job


def _make_final_state(**overrides) -> dict:
    writer_output = WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Shipped X, improving Y by 30%.", "Led Z."]),
            RoleBullets(index=1, bullets=["Built W."]),
        ]
    )
    state = {
        "writer_output": writer_output,
        "best_latex": "",
        "aggregate_score": 87.5,
        "passed": True,
        "tuning": PipelineTuning.defaults(),
        "panel_scores": [],
    }
    state.update(overrides)
    return state


@pytest.fixture
def settings(tmp_path, monkeypatch) -> VaultSettings:
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    return VaultSettings.load()


def test_disabled_vault_returns_none_and_writes_nothing(monkeypatch):
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)
    disabled = VaultSettings.load()
    assert disabled.enabled is False

    result = write_run_note(
        _make_job(), _make_final_state(), "backend", [], settings=disabled
    )

    assert result is None


def test_writes_frontmatter_with_expected_fields_and_types(settings):
    job = _make_job()
    job.obsidian_learn = True

    path = write_run_note(
        job, _make_final_state(), "backend", ["ai", "fintech"], settings=settings
    )

    assert path is not None
    fm = read_note(path).frontmatter

    assert fm["job_id"] == job.job_id
    assert fm["label"] == job.label
    assert fm["jd_name"] == job.jd_name
    assert fm["role"] == "backend"
    assert fm["domains"] == ["ai", "fintech"]
    assert fm["jd_type"] == ["backend", "ai", "fintech"]
    assert isinstance(fm["created"], str) and fm["created"]
    assert fm["internal_score"] == 87.5
    assert fm["passed"] is True
    assert fm["threshold_used"] == PipelineTuning.defaults().threshold
    assert fm["rubric_weights_used"] == dict(PipelineTuning.defaults().rubric_weights)
    assert fm["bullet_shapes_used"] == ["punchy"]
    assert fm["learning_used"] is True
    assert fm["outcome"] == "pending"
    assert fm["outcome_date"] == ""


def test_role_none_produces_none_role_and_domains_only_jd_type(settings):
    job = _make_job()

    path = write_run_note(job, _make_final_state(), None, [], settings=settings)

    fm = read_note(path).frontmatter
    assert fm["role"] is None
    assert fm["domains"] == []
    assert fm["jd_type"] == []


def test_role_none_with_domains_derives_jd_type_from_domains_only(settings):
    job = _make_job()

    path = write_run_note(job, _make_final_state(), None, ["ai"], settings=settings)

    fm = read_note(path).frontmatter
    assert fm["role"] is None
    assert fm["domains"] == ["ai"]
    assert fm["jd_type"] == ["ai"]


def test_final_bullets_section_contains_each_bullet_verbatim(settings):
    job = _make_job()

    path = write_run_note(job, _make_final_state(), "backend", [], settings=settings)

    body = read_note(path).body
    assert "## Final bullets" in body
    assert "Shipped X, improving Y by 30%." in body
    assert "Led Z." in body
    assert "Built W." in body


def test_rewriting_preserves_existing_outcome_and_outcome_date(settings):
    job = _make_job()
    path = write_run_note(job, _make_final_state(), "backend", [], settings=settings)

    note = read_note(path)
    note.frontmatter["outcome"] = "interview"
    note.frontmatter["outcome_date"] = "2026-08-01"
    write_note(path, note.frontmatter, note.body)

    second_path = write_run_note(
        job, _make_final_state(aggregate_score=91.0), "backend", [], settings=settings
    )

    assert second_path == path
    fm = read_note(second_path).frontmatter
    assert fm["outcome"] == "interview"
    assert fm["outcome_date"] == "2026-08-01"
    assert fm["internal_score"] == 91.0


def test_slug_is_filesystem_safe_and_stable_for_same_job(settings):
    job = _make_job(label="Sr. Backend Engineer (Remote!) @ Acme/Co")

    first = write_run_note(job, _make_final_state(), "backend", [], settings=settings)
    second = write_run_note(job, _make_final_state(), "backend", [], settings=settings)

    assert first is not None
    assert first == second
    assert " " not in first.name
    stem = first.name.removesuffix(".md")
    assert all(c.isalnum() or c == "-" for c in stem)


def test_falls_back_to_parsing_bullets_from_latex_when_no_writer_output(settings):
    job = _make_job()
    latex = (
        "\\begin{itemize}\n"
        "  \\item Improved throughput by 40\\%.\n"
        "  \\item Mentored two engineers.\n"
        "\\end{itemize}\n"
    )
    state = _make_final_state(writer_output=None, best_latex=latex)

    path = write_run_note(job, state, "backend", [], settings=settings)

    body = read_note(path).body
    assert "Improved throughput by 40" in body
    assert "Mentored two engineers." in body
