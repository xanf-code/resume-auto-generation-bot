"""Phase 8 - API-boundary DTO validation + web settings defaults."""
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


# --- Per-application tuning DTO ----------------------------------------------


def _weights(**over):
    base = {
        "keyword_match": 0.30,
        "impact_quality": 0.20,
        "coherence": 0.20,
        "plausibility": 0.15,
        "formatting": 0.15,
    }
    base.update(over)
    return base


def test_job_submit_tuning_defaults_to_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j")
    assert r.tuning is None


def test_tuning_dto_normalizes_weights_to_sum_one():
    from src.web.schemas import TuningDTO
    # Weights that sum to 2.0 → each halved so they sum to 1.0.
    dto = TuningDTO(
        threshold=78,
        plausibility_floor=20,
        max_iterations=4,
        max_compile_retries=2,
        max_identity_retries=2,
        max_length_retries=3,
        rubric_weights=_weights(
            keyword_match=0.60, impact_quality=0.40, coherence=0.40,
            plausibility=0.30, formatting=0.30,
        ),
    )
    w = dto.rubric_weights
    assert sum(vars(w).values()) == pytest.approx(1.0)
    assert w.keyword_match == pytest.approx(0.30)


def test_tuning_dto_rejects_all_zero_weights():
    from src.web.schemas import TuningDTO
    with pytest.raises(ValidationError):
        TuningDTO(
            threshold=78, plausibility_floor=20, max_iterations=4,
            max_compile_retries=2, max_identity_retries=2, max_length_retries=3,
            rubric_weights=_weights(
                keyword_match=0.0, impact_quality=0.0, coherence=0.0,
                plausibility=0.0, formatting=0.0,
            ),
        )


def test_tuning_dto_rejects_out_of_range_threshold():
    from src.web.schemas import TuningDTO
    with pytest.raises(ValidationError):
        TuningDTO(
            threshold=150, plausibility_floor=20, max_iterations=4,
            max_compile_retries=2, max_identity_retries=2, max_length_retries=3,
            rubric_weights=_weights(),
        )


def test_tuning_dto_rejects_zero_iterations():
    from src.web.schemas import TuningDTO
    with pytest.raises(ValidationError):
        TuningDTO(
            threshold=78, plausibility_floor=20, max_iterations=0,
            max_compile_retries=2, max_identity_retries=2, max_length_retries=3,
            rubric_weights=_weights(),
        )


def test_tuning_dto_to_tuning_maps_all_fields():
    from src.web.schemas import TuningDTO
    from src.pipeline.tuning import PipelineTuning
    dto = TuningDTO(
        threshold=85, plausibility_floor=30, max_iterations=6,
        max_compile_retries=1, max_identity_retries=3, max_length_retries=4,
        rubric_weights=_weights(),
    )
    t = dto.to_tuning()
    assert isinstance(t, PipelineTuning)
    assert t.threshold == 85
    assert t.plausibility_floor == 30
    assert t.max_iterations == 6
    assert t.max_compile_retries == 1
    assert t.max_identity_retries == 3
    assert t.max_length_retries == 4
    assert dict(t.rubric_weights) == pytest.approx(_weights())


# --- bullet_shapes field on JobSubmitRequest -----------------------------------


def test_bullet_shapes_absent_defaults_to_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j")
    assert r.bullet_shapes is None


def test_bullet_shapes_empty_list_normalizes_to_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", bullet_shapes=[])
    assert r.bullet_shapes is None


def test_bullet_shapes_rejects_unknown_name():
    from src.web.schemas import JobSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="t", jd_text="j", bullet_shapes=["INVALID"])


def test_bullet_shapes_rejects_partial_unknown():
    from src.web.schemas import JobSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="t", jd_text="j", bullet_shapes=["PAR", "INVALID"])


def test_bullet_shapes_valid_single():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", bullet_shapes=["PAR"])
    assert r.bullet_shapes == ["PAR"]


def test_bullet_shapes_valid_subset():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(
        label="X", resume_tex="t", jd_text="j",
        bullet_shapes=["PAR", "RESULT-FIRST"],
    )
    assert r.bullet_shapes == ["PAR", "RESULT-FIRST"]


def test_bullet_shapes_all_four_accepted():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(
        label="X", resume_tex="t", jd_text="j",
        bullet_shapes=["PAR", "RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"],
    )
    assert r.bullet_shapes == ["PAR", "RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"]


def test_bullet_shapes_deduplicates_preserving_order():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(
        label="X", resume_tex="t", jd_text="j",
        bullet_shapes=["PAR", "RESULT-FIRST", "PAR"],
    )
    assert r.bullet_shapes == ["PAR", "RESULT-FIRST"]


def test_bullet_shapes_none_explicitly_stays_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", bullet_shapes=None)
    assert r.bullet_shapes is None
