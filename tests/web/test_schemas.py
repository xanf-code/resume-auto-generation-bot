"""Phase 8 — API-boundary DTO validation + web settings defaults."""
import pytest
from pydantic import ValidationError


def test_job_submit_rejects_blank_resume():
    from src.web.schemas import JobSubmitRequest
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="   ", jd_text="jd")


def test_job_submit_rejects_blank_jd():
    from src.web.schemas import JobSubmitRequest
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="tex", jd_text="")


def test_job_submit_requires_label():
    from src.web.schemas import JobSubmitRequest
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="   ", resume_tex="tex", jd_text="jd")


def test_job_submit_trims_label():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="  Amazon SDE  ", resume_tex="tex", jd_text="jd")
    assert r.label == "Amazon SDE"


def test_job_rename_trims_and_rejects_blank():
    from src.web.schemas import JobRenameRequest
    from pydantic import ValidationError

    r = JobRenameRequest(label="  Vestwell  ")
    assert r.label == "Vestwell"
    with pytest.raises(ValidationError):
        JobRenameRequest(label="   ")


def test_job_submit_defaults_enable_scoring_false():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j")
    assert r.enable_scoring is False


def test_skilldump_dto_total_is_sum_of_buckets():
    from src.web.schemas import SkillDumpDTO
    dto = SkillDumpDTO(
        language_and_framework=["Python", "Go"],
        infrastructure=["AWS"],
        database=[],
        ai_tools=["RAG"],
    )
    assert dto.total == 4
    # total must serialize (computed field) for the /skills endpoint
    assert dto.model_dump()["total"] == 4


def test_web_settings_defaults():
    from src.web.config import WebSettings
    s = WebSettings()
    assert s.max_concurrent_jobs == 3
    assert s.out_root == "out"
    assert s.event_buffer_max == 500
