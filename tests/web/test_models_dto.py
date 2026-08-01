"""Per-job model config - ModelsDTO → PipelineModels → model_context."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.db.repository import InMemoryResumeRepository


def _role(
    model: str, effort: str | None = None, extra_params: dict | None = None
) -> dict:
    return {"model": model, "effort": effort, "extra_params": extra_params}


def _models(**over) -> dict:
    base = {
        "writer": _role("anthropic/claude-sonnet-5", "medium"),
        "parser": _role("openai/gpt-4o-mini"),
        "gap": _role("anthropic/claude-opus-5", "medium"),
        "skills": _role("openai/gpt-4o-mini"),
        "scoring": _role("openai/gpt-4o-mini"),
    }
    base.update(over)
    return base


def test_models_dto_to_pipeline_models_preserves_none_effort():
    from src.web.schemas import ModelsDTO

    dto = ModelsDTO(
        **_models(
            writer=_role("anthropic/claude-opus-5", "none"),
            gap=_role("anthropic/claude-opus-5", "none"),
        )
    )
    pm = dto.to_pipeline_models()
    assert pm.writer.effort == "none"
    assert pm.gap.effort == "none"


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
    assert pm.skills.model == "openai/gpt-4o-mini"
    assert pm.skills.effort is None
    assert pm.scoring.model == "openai/gpt-4o-mini"


def test_models_dto_to_pipeline_models_preserves_extra_params():
    from src.web.schemas import ModelsDTO

    dto = ModelsDTO(
        **_models(
            writer=_role("anthropic/claude-sonnet-5", "medium", {"temperature": 0.7}),
            parser=_role("openai/gpt-4o-mini", None, {"temperature": 0.0}),
            gap=_role(
                "anthropic/claude-opus-5", "medium",
                {"temperature": 0.5, "top_k": 40},
            ),
            skills=_role("openai/gpt-4o-mini", None, {"temperature": 0.2}),
            scoring=_role("openai/gpt-4o-mini", None, {"temperature": 0.2}),
        )
    )
    pm = dto.to_pipeline_models()
    assert pm.writer.extra_params == {"temperature": 0.7}
    assert pm.parser.extra_params == {"temperature": 0.0}
    assert pm.gap.extra_params == {"temperature": 0.5, "top_k": 40}
    assert pm.skills.extra_params == {"temperature": 0.2}
    assert pm.scoring.extra_params == {"temperature": 0.2}


def test_models_dto_to_pipeline_models_extra_params_defaults_to_none():
    from src.web.schemas import ModelsDTO

    dto = ModelsDTO(**_models())
    pm = dto.to_pipeline_models()
    assert pm.writer.extra_params is None
    assert pm.parser.extra_params is None
    assert pm.gap.extra_params is None
    assert pm.skills.extra_params is None
    assert pm.scoring.extra_params is None


def test_models_dto_skills_omitted_falls_back_to_none_extra_params():
    """Older payloads without skills still convert; skills.extra_params is None."""
    from src.web.schemas import ModelsDTO

    payload = {
        "writer": _role("anthropic/claude-sonnet-5", "medium"),
        "parser": _role("openai/gpt-4o-mini"),
        "gap": _role("anthropic/claude-opus-5", "medium"),
        "scoring": _role("openai/gpt-4o-mini"),
    }
    pm = ModelsDTO(**payload).to_pipeline_models()
    assert pm.skills.extra_params is None


def test_model_role_rejects_blank_extra_param_key():
    from src.web.schemas import ModelRoleDTO

    with pytest.raises(ValidationError):
        ModelRoleDTO(model="anthropic/claude-opus-5", extra_params={"  ": 0.7})


def test_model_role_rejects_reserved_extra_param_keys():
    from src.web.schemas import ModelRoleDTO

    for reserved in ("effort", "reasoning", "model", "provider"):
        with pytest.raises(ValidationError):
            ModelRoleDTO(model="anthropic/claude-opus-5", extra_params={reserved: "x"})


def test_model_role_accepts_arbitrary_extra_params():
    from src.web.schemas import ModelRoleDTO

    dto = ModelRoleDTO(
        model="anthropic/claude-opus-5",
        extra_params={"temperature": 0.0, "top_k": 40, "top_p": 0.9, "seed": 7},
    )
    assert dto.extra_params == {"temperature": 0.0, "top_k": 40, "top_p": 0.9, "seed": 7}


def test_model_role_extra_params_defaults_to_none():
    from src.web.schemas import ModelRoleDTO

    dto = ModelRoleDTO(model="anthropic/claude-opus-5")
    assert dto.extra_params is None


def test_model_role_treats_empty_extra_params_as_none():
    from src.web.schemas import ModelRoleDTO

    dto = ModelRoleDTO(model="anthropic/claude-opus-5", extra_params={})
    assert dto.extra_params is None


def test_models_dto_skills_defaults_when_omitted():
    """Older payloads without skills still convert; skills falls back to MODEL_SKILLS."""
    from config import settings
    from src.web.schemas import ModelsDTO

    payload = {
        "writer": _role("anthropic/claude-sonnet-5", "medium"),
        "parser": _role("openai/gpt-4o-mini"),
        "gap": _role("anthropic/claude-opus-5", "medium"),
        "scoring": _role("openai/gpt-4o-mini"),
    }
    pm = ModelsDTO(**payload).to_pipeline_models()
    assert pm.skills.model == settings.MODEL_SKILLS
    assert pm.skills.effort is None


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

    for effort in ("none", "minimal", "low", "medium", "high", "xhigh", "max"):
        dto = ModelRoleDTO(model="anthropic/claude-opus-5", effort=effort)
        assert dto.effort == effort


def test_model_role_accepts_none_effort_string():
    """OpenRouter effort 'none' disables reasoning; must pass DTO validation."""
    from src.web.schemas import ModelRoleDTO

    dto = ModelRoleDTO(model="anthropic/claude-opus-5", effort="none")
    assert dto.effort == "none"


def test_job_manager_persists_models():
    from src.web.job_manager import JobManager
    from src.web.config import WebSettings
    from src.web.schemas import JobSubmitRequest, ModelsDTO
    from unittest.mock import patch

    settings = WebSettings(
        max_concurrent_jobs=1, out_root="/tmp/resumebot_models_test", event_buffer_max=50
    )
    manager = JobManager(settings, repo=InMemoryResumeRepository())

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
    from src.pipeline.llm import (
        _ctx_effort_skills,
        _ctx_effort_strong,
        _ctx_extra_scoring,
        _ctx_extra_strong,
        _ctx_model_fast,
        _ctx_model_scoring,
        _ctx_model_skills,
        _ctx_model_strong,
    )
    from src.pipeline.models import ModelRole, PipelineModels
    from src.web.config import WebSettings
    from src.web.job import Job
    from src.web.job_manager import JobManager
    from src.web.schemas import JobStatus

    settings = WebSettings(
        max_concurrent_jobs=1, out_root="/tmp/resumebot_models_ctx", event_buffer_max=50
    )
    manager = JobManager(settings, repo=InMemoryResumeRepository())
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    manager.bind_loop(loop)

    captured: dict = {}

    def capturing_pipeline(**kwargs):
        captured["fast"] = _ctx_model_fast.get()
        captured["strong"] = _ctx_model_strong.get()
        captured["skills"] = _ctx_model_skills.get()
        captured["scoring"] = _ctx_model_scoring.get()
        captured["effort_strong"] = _ctx_effort_strong.get()
        captured["effort_skills"] = _ctx_effort_skills.get()
        captured["extra_strong"] = _ctx_extra_strong.get()
        captured["extra_scoring"] = _ctx_extra_scoring.get()
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
        writer=ModelRole("anthropic/claude-opus-5", "high", {"temperature": 0.7}),
        parser=ModelRole("openai/gpt-4o-mini", None),
        gap=ModelRole("anthropic/claude-opus-5", "medium"),
        skills=ModelRole("deepseek/deepseek-v4-flash", None),
        scoring=ModelRole("openai/gpt-4o-mini", "low", {"temperature": 0.2}),
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
    assert captured["skills"] == "deepseek/deepseek-v4-flash"
    assert captured["scoring"] == "openai/gpt-4o-mini"
    assert captured["effort_strong"] == "high"
    assert captured["effort_skills"] is None
    assert captured["extra_strong"] == {"temperature": 0.7}
    assert captured["extra_scoring"] == {"temperature": 0.2}

    loop.call_soon_threadsafe(loop.stop)


def test_pipeline_models_defaults_include_skills():
    from src.pipeline.models import PipelineModels
    from config import settings

    pm = PipelineModels.defaults()
    assert pm.skills.model == settings.MODEL_SKILLS
    assert pm.skills.effort is None
    assert pm.scoring.model == settings.MODEL_SCORING


def test_pipeline_models_defaults_leave_extra_params_none():
    """No config.settings constants exist for extra params - defaults() omits
    them for every role, matching parse_*'s "no override -> not sent"
    behavior. Only explicit per-run overrides (e.g. from the frontend) set it."""
    from src.pipeline.models import PipelineModels

    pm = PipelineModels.defaults()
    assert pm.writer.extra_params is None
    assert pm.parser.extra_params is None
    assert pm.gap.extra_params is None
    assert pm.skills.extra_params is None
    assert pm.scoring.extra_params is None
