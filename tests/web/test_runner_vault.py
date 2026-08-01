"""Phase 7/10 - integration tests for run_job's Obsidian vault wiring.

Exercises the full seam: JD tagging always runs and returns a role/domains
split, retrieval + tuning resolution run only when ``job.obsidian_learn`` is
True, and the run note is always written regardless. The pipeline itself is
monkeypatched at the ``stream_pipeline`` boundary (the existing hermetic
pattern from tests/web/test_job_manager.py) so no LLM calls happen.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import src.web.runner as runner_module
from src.agents.jd_tagger import JdClassification
from src.db.models import JobRecord
from src.db.repository import InMemoryResumeRepository
from src.pipeline.schemas import RoleBullets, WriterOutput
from src.vault.notes import read_note, write_note
from src.web.config import WebSettings
from src.web.job import Job
from src.web.job_manager import JobManager
from src.web.runner import run_job
from src.web.schemas import JobStatus


def _make_settings(**kwargs) -> WebSettings:
    defaults = dict(max_concurrent_jobs=3, out_root="/tmp/resumebot_test_vault", event_buffer_max=500)
    defaults.update(kwargs)
    return WebSettings(**defaults)


def _make_manager(**settings_kwargs) -> JobManager:
    return JobManager(_make_settings(**settings_kwargs), repo=InMemoryResumeRepository())


def _seed_job(manager: JobManager, **overrides) -> Job:
    defaults = dict(
        label="New Role @ Acme",
        jd_raw="We need a backend engineer.",
        jd_name="new-jd",
        resume_tex_raw="\\documentclass{article}",
    )
    defaults.update(overrides)
    job = Job(**defaults)
    manager._repo.create(
        JobRecord(
            job_id=job.job_id,
            label=job.label,
            status="queued",
            created_at=job.created_at,
        )
    )
    return job


def _seed_winning_backend_notes(vault_dir: Path) -> None:
    """Two past `interview` runs role-tagged `backend`, plus a threshold override."""
    for i in range(2):
        write_note(
            vault_dir / "runs" / f"2026-01-0{i + 1}-old-role-{i}.md",
            {
                "job_id": f"old-job-{i}",
                "label": f"Old Role {i}",
                "jd_name": "old-jd",
                "role": "backend",
                "domains": [],
                "jd_type": ["backend"],
                "created": f"2026-01-0{i + 1}T00:00:00+00:00",
                "internal_score": 90.0,
                "passed": True,
                "outcome": "interview",
                "outcome_date": "2026-01-10",
            },
            "## Final bullets\nShipped a proven backend bullet.\n\n"
            "## Score breakdown\n- Aggregate: 90.0\n",
        )

    tuning_dir = vault_dir / "tuning"
    tuning_dir.mkdir(parents=True, exist_ok=True)
    (tuning_dir / "active.json").write_text(json.dumps({"by_tag": {"backend": {"threshold": 91}}}))


def _seed_winning_product_note(vault_dir: Path) -> None:
    """A past `interview` run role-tagged `product`."""
    write_note(
        vault_dir / "runs" / "2026-01-05-old-product-role.md",
        {
            "job_id": "old-product-job",
            "label": "Old Product Role",
            "jd_name": "old-product-jd",
            "role": "product",
            "domains": [],
            "jd_type": ["product"],
            "created": "2026-01-05T00:00:00+00:00",
            "internal_score": 88.0,
            "passed": True,
            "outcome": "interview",
            "outcome_date": "2026-01-15",
        },
        "## Final bullets\nShipped a proven product bullet.\n\n"
        "## Score breakdown\n- Aggregate: 88.0\n",
    )


def _find_note_by_job_id(vault_dir: Path, job_id: str):
    runs_dir = vault_dir / "runs"
    if not runs_dir.is_dir():
        return None
    for path in runs_dir.glob("*.md"):
        note = read_note(path)
        if note.frontmatter.get("job_id") == job_id:
            return note
    return None


def _fake_pipeline(final_state: dict, captured: dict):
    def fake(resume_tex_raw, jd_raw, out_dir, jd_name, enable_scoring, on_step=None, write_files=None, **kwargs):
        captured["seen"] = True
        captured.update(kwargs)
        state = dict(final_state)
        if "tuning" in kwargs:
            state["tuning"] = kwargs["tuning"]
        return state

    return fake


_WRITER_STATE = {
    "writer_output": WriterOutput(roles=[RoleBullets(index=0, bullets=["Wrote a brand-new bullet."])]),
    "best_latex": "",
    "aggregate_score": 85.0,
    "passed": True,
    "output_pdf": None,
}


# ---------------------------------------------------------------------------
# learn ON - retrieval + tuning override applied, diff logged, note written
# ---------------------------------------------------------------------------

def test_run_job_learn_on_seeds_examples_and_tuning_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert job.role == "backend"
    assert job.domains == []

    # Classification and terminal status both survive in the repository row -
    # not just on the ephemeral runtime job.
    rec = manager._repo.get(job.job_id)
    assert rec.role == "backend"
    assert rec.domains == []
    assert rec.status == "done"
    assert rec.finished_at is not None

    # Writer's prompt input carried the seeded bullet from the winning run.
    assert captured.get("proven_examples") is not None
    assert "Shipped a proven backend bullet." in captured["proven_examples"]

    # The vault's by_tag override for "backend" won over the pipeline default.
    assert captured["tuning"].threshold == 91

    note = _find_note_by_job_id(tmp_path, job.job_id)
    assert note is not None
    assert note.frontmatter["outcome"] == "pending"
    assert note.frontmatter["learning_used"] is True
    assert note.frontmatter["role"] == "backend"
    assert note.frontmatter["domains"] == []


def test_run_job_learn_on_logs_tuning_diff_to_activity_stream(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    events = job.events.since(0)
    assert any(e.detail and "threshold" in e.detail for e in events)


def test_run_job_learn_on_logs_retrieval_hit_to_activity_stream(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    events = job.events.since(0)
    retrieval = [e for e in events if e.stage == "vault_retrieval"]
    assert len(retrieval) == 1
    assert "found proven examples" in retrieval[0].detail


def test_run_job_learn_on_logs_retrieval_miss_to_activity_stream(tmp_path, monkeypatch):
    """Vault enabled, learning on, but nothing matches the role - still logged."""
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    events = job.events.since(0)
    retrieval = [e for e in events if e.stage == "vault_retrieval"]
    assert len(retrieval) == 1
    assert "no proven examples yet" in retrieval[0].detail


def test_run_job_logs_vault_write_to_activity_stream(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    events = job.events.since(0)
    write_events = [e for e in events if e.stage == "vault_write"]
    assert len(write_events) == 1
    assert "saved run note" in write_events[0].detail


def test_run_job_learn_on_no_vault_match_omits_diff_event(tmp_path, monkeypatch):
    """A role with no by_tag override still runs learn-on, but logs no diff."""
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    events = job.events.since(0)
    assert not any(e.stage == "tuning" for e in events)


def test_run_job_role_gate_only_retrieves_matching_role(tmp_path, monkeypatch):
    """A seeded product win + a seeded backend win; a product JD run only
    retrieves the product win's bullet, never the backend one (the actual
    production bug being fixed).
    """
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)
    _seed_winning_product_note(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager, jd_raw="We need a product owner.")
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="product", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert job.role == "product"
    assert captured.get("proven_examples") is not None
    assert "Shipped a proven product bullet." in captured["proven_examples"]
    assert "Shipped a proven backend bullet." not in captured["proven_examples"]


# ---------------------------------------------------------------------------
# learn OFF - no retrieval, no tuning override; note still always written
# ---------------------------------------------------------------------------

def test_run_job_learn_off_skips_retrieval_and_tuning_but_still_writes_note(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = False

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert captured.get("seen") is True
    assert "proven_examples" not in captured
    assert captured.get("tuning") is None  # job.tuning was None and learning is off

    # Role/domains are still computed - the note always needs them - even with learning off.
    assert job.role == "backend"
    assert job.domains == []

    note = _find_note_by_job_id(tmp_path, job.job_id)
    assert note is not None
    assert note.frontmatter["learning_used"] is False
    assert note.frontmatter["role"] == "backend"


def test_run_job_learn_off_with_explicit_job_tuning_passes_it_through(tmp_path, monkeypatch):
    from src.pipeline.tuning import PipelineTuning

    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    _seed_winning_backend_notes(tmp_path)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    explicit = PipelineTuning.defaults()
    job = _seed_job(manager, tuning=explicit)
    job.obsidian_learn = False

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert captured["tuning"] is explicit


# ---------------------------------------------------------------------------
# Vault errors never fail the run
# ---------------------------------------------------------------------------

def test_run_job_write_run_note_error_does_not_fail_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ), \
         patch.object(runner_module, "write_run_note", side_effect=RuntimeError("disk exploded")):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert job.error is None


def test_run_job_retrieval_error_falls_back_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.obsidian_learn = True

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ), \
         patch.object(runner_module, "retrieve_examples", side_effect=RuntimeError("vault read failed")):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert job.error is None
    assert captured.get("proven_examples") is None


# ---------------------------------------------------------------------------
# classify_jd_type must run inside model_context, and its result must be
# threaded into stream_pipeline as jd_domains (not recomputed by analyze_jd)
# ---------------------------------------------------------------------------
#
# Regression: classify_jd_type() used to be called before model_context was
# entered, so it always fell back to config.settings.MODEL_FAST regardless of
# the job's configured Parser model/effort/params - and analyze_jd's node
# independently called classify_jd_type a second time (inside model_context),
# duplicating the LLM call and risking disagreement between the two results.


def test_run_job_seeds_jd_domains_from_classification_into_pipeline(tmp_path, monkeypatch):
    """The classification computed for role/domain tagging must be handed to
    stream_pipeline as jd_domains, so analyze_jd's node reuses it instead of
    calling classify_jd_type a second, independent time."""
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=["fintech", "ai"]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert captured["jd_domains"] == ["fintech", "ai"]


def test_run_job_seeds_empty_jd_domains_list_into_pipeline(tmp_path, monkeypatch):
    """An explicit empty list (JD tagged no domains) must still be forwarded -
    analyze_jd distinguishes an empty seeded list from the key being absent."""
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert captured["jd_domains"] == []


def test_run_job_classify_jd_type_respects_model_context_override(tmp_path, monkeypatch):
    """classify_jd_type's underlying parse_fast call must resolve against the
    job's configured Parser model/effort/extra_params - not the bare
    config.settings.MODEL_FAST default - because it now runs inside the same
    model_context as the rest of the pipeline.

    This module's autouse ``_no_real_jd_tagging`` fixture (tests/web/conftest.py)
    stubs ``runner_module.classify_jd_type`` for every other test in this file
    to keep them hermetic; this test explicitly restores the real
    implementation since it's the one place that needs to exercise its actual
    model resolution.
    """
    import src.agents.jd_tagger as jd_tagger_module
    from src.pipeline.llm import effective_fast
    from src.pipeline.models import ModelRole, PipelineModels
    from src.pipeline.schemas import JDTags

    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    monkeypatch.setattr(runner_module, "classify_jd_type", jd_tagger_module.classify_jd_type)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)
    job.models = PipelineModels(
        writer=ModelRole("anthropic/claude-opus-5", "high"),
        parser=ModelRole("openai/gpt-oss-20b", "low", {"temperature": 0.0}),
        gap=ModelRole("anthropic/claude-opus-5", "medium"),
        skills=ModelRole("deepseek/deepseek-v4-flash", None),
        scoring=ModelRole("openai/gpt-4o-mini", None),
    )

    captured_role: dict = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured_role["role"] = effective_fast()
        return JDTags(role="backend", domains=[])

    monkeypatch.setattr(jd_tagger_module, "parse_fast", fake_parse_fast)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert captured_role["role"].model == "openai/gpt-oss-20b"
    assert captured_role["role"].effort == "low"
    assert captured_role["role"].extra_params == {"temperature": 0.0}


def test_run_job_disabled_vault_still_computes_role_and_writes_no_note(tmp_path, monkeypatch):
    """RESUME_VAULT_DIR unset - the vault is a no-op, but tagging still runs."""
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)

    manager = _make_manager(out_root=str(tmp_path / "out"))
    job = _seed_job(manager)

    captured: dict = {}
    fake = _fake_pipeline(_WRITER_STATE, captured)

    with patch.object(runner_module.main_module, "stream_pipeline", side_effect=fake), \
         patch.object(
             runner_module,
             "classify_jd_type",
             return_value=JdClassification(role="backend", domains=[]),
         ):
        run_job(job, manager)

    assert job.status == JobStatus.DONE
    assert job.role == "backend"
    assert captured.get("proven_examples") is None

    # No vault, no console noise - neither the retrieval nor the write event fires.
    events = job.events.since(0)
    assert not any(e.stage in ("vault_retrieval", "vault_write") for e in events)
