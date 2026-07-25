"""Per-job model config - ModelsDTO → PipelineModels → model_context."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _role(model: str, effort: str | None = None) -> dict:
    return {"model": model, "effort": effort}


def _models(**over) -> dict:
    base = {
        "writer": _role("anthropic/claude-sonnet-5", "medium"),
        "parser": _role("openai/gpt-4o-mini"),
        "gap": _role("anthropic/claude-opus-5", "medium"),
        "scoring": _role("openai/gpt-4o-mini"),
    }
    base.update(over)
    return base


def test_job_submit_models_defaults_to_none():
    from src.web.schemas import JobSubmitRequest

    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j")
    assert r.models is None


def test_models_dto_to_pipeline_models():
    from src.web.schemas import ModelsDTO
    from src.pipeline.models import PipelineModels

    dto = ModelsDTO(**_models())
    pm = dto.to_pipeline_models()
    assert isinstance(pm, PipelineModels)
    assert pm.writer.model == "anthropic/claude-sonnet-5"
    assert pm.writer.effort == "medium"
    assert pm.parser.model == "openai/gpt-4o-mini"
    assert pm.parser.effort is None
    assert pm.gap.model == "anthropic/claude-opus-5"
    assert pm.scoring.model == "openai/gpt-4o-mini"


def test_model_role_rejects_blank_model():
    from src.web.schemas import ModelRoleDTO

    with pytest.raises(ValidationError):
        ModelRoleDTO(model="   ", effort=None)


def test_model_role_rejects_unknown_effort():
    from src.web.schemas import ModelRoleDTO

    with pytest.raises(ValidationError):
        ModelRoleDTO(model="anthropic/claude-opus-5", effort="super-high")


def test_model_role_accepts_known_efforts():
    from src.web.schemas import ModelRoleDTO

    for effort in ("minimal", "low", "medium", "high", "xhigh", "max"):
        dto = ModelRoleDTO(model="anthropic/claude-opus-5", effort=effort)
        assert dto.effort == effort


def test_job_manager_persists_models():
    from src.web.job_manager import JobManager
    from src.web.config import WebSettings
    from src.web.schemas import JobSubmitRequest, ModelsDTO
    from unittest.mock import patch

    settings = WebSettings(
        max_concurrent_jobs=1, out_root="/tmp/resumebot_models_test", event_buffer_max=50
    )
    manager = JobManager(settings)

    with patch("src.web.job_manager.run_job", lambda job, mgr: None):
        job = manager.submit(
            JobSubmitRequest(
                label="X",
                resume_tex="t",
                jd_text="j",
                models=ModelsDTO(**_models()),
            )
        )

    assert job.models is not None
    assert job.models.writer.model == "anthropic/claude-sonnet-5"
    assert job.models.parser.effort is None


def test_runner_wraps_pipeline_in_model_context():
    """When job.models is set, run_job enters model_context with those slugs/efforts."""
    import asyncio
    import threading
    import time
    from unittest.mock import patch

    import src.web.runner as runner_module
    from src.pipeline.llm import _ctx_model_fast, _ctx_model_strong, _ctx_effort_strong
    from src.pipeline.models import ModelRole, PipelineModels
    from src.web.config import WebSettings
    from src.web.job import Job
    from src.web.job_manager import JobManager
    from src.web.schemas import JobStatus

    settings = WebSettings(
        max_concurrent_jobs=1, out_root="/tmp/resumebot_models_ctx", event_buffer_max=50
    )
    manager = JobManager(settings)
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    manager.bind_loop(loop)

    captured: dict = {}

    def capturing_pipeline(**kwargs):
        captured["fast"] = _ctx_model_fast.get()
        captured["strong"] = _ctx_model_strong.get()
        captured["effort_strong"] = _ctx_effort_strong.get()
        return {
            "best_latex": "x",
            "aggregate_score": 80.0,
            "passed": True,
            "output_pdf": "x.pdf",
        }

    job = Job(label="X", status=JobStatus.QUEUED)
    job.resume_tex_raw = "t"
    job.jd_raw = "j"
    job.jd_name = "X"
    job.models = PipelineModels(
        writer=ModelRole("anthropic/claude-opus-5", "high"),
        parser=ModelRole("openai/gpt-4o-mini", None),
        gap=ModelRole("anthropic/claude-opus-5", "medium"),
        scoring=ModelRole("openai/gpt-4o-mini", None),
    )

    with patch.object(
        runner_module.main_module, "stream_pipeline", side_effect=capturing_pipeline
    ):
        runner_module.run_job(job, manager)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and job.status not in (
        JobStatus.DONE,
        JobStatus.FAILED,
    ):
        time.sleep(0.05)

    assert job.status == JobStatus.DONE, job.error
    assert captured["fast"] == "openai/gpt-4o-mini"
    assert captured["strong"] == "anthropic/claude-opus-5"
    assert captured["effort_strong"] == "high"

    loop.call_soon_threadsafe(loop.stop)
