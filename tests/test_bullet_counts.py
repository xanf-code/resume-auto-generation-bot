"""Per-role bullet budget — TDD tests.

Tests for:
- DEFAULT_ROLE_BULLET_COUNTS constant in config.settings
- build_bullet_budget_directive in src.agents.writer
- validate_bullet_counts in src.agents.validators
- check_bullet_lengths node wires count violations through
- PipelineState.role_bullet_counts channel
- WRITER_SYSTEM no longer carries hardcoded counts in rule 7
- build_writer_user_message injects ## BULLET BUDGET
"""
import pytest


# ---------------------------------------------------------------------------
# config.settings — default constant
# ---------------------------------------------------------------------------

def test_default_role_bullet_counts_is_four_four():
    from config.settings import DEFAULT_ROLE_BULLET_COUNTS
    assert DEFAULT_ROLE_BULLET_COUNTS == [4, 4]


# ---------------------------------------------------------------------------
# build_bullet_budget_directive — None → default [4, 4]
# ---------------------------------------------------------------------------

def test_build_bullet_budget_directive_none_uses_defaults():
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive(None)
    assert "EXACTLY 4 bullets for role index 0" in d
    assert "EXACTLY 4 bullets for role index 1" in d
    assert "8 bullets total" in d


def test_build_bullet_budget_directive_empty_list_uses_defaults():
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive([])
    assert "EXACTLY 4 bullets for role index 0" in d
    assert "EXACTLY 4 bullets for role index 1" in d


def test_build_bullet_budget_directive_none_and_empty_are_identical():
    from src.agents.writer import build_bullet_budget_directive
    assert build_bullet_budget_directive(None) == build_bullet_budget_directive([])


# ---------------------------------------------------------------------------
# build_bullet_budget_directive — custom counts
# ---------------------------------------------------------------------------

def test_build_bullet_budget_directive_custom_counts():
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive([3, 2])
    assert "EXACTLY 3 bullets for role index 0" in d
    assert "EXACTLY 2 bullets for role index 1" in d
    assert "5 bullets total" in d


def test_build_bullet_budget_directive_single_count_single_role():
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive([5])
    assert "EXACTLY 5 bullets for role index 0" in d
    assert "5 bullets total" in d
    assert "role index 1" not in d


def test_build_bullet_budget_directive_total_equals_sum():
    """The 'N bullets total' line must always be the sum of the list."""
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive([3, 4])
    assert "7 bullets total" in d


def test_build_bullet_budget_directive_three_roles():
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive([4, 3, 2])
    assert "EXACTLY 4 bullets for role index 0" in d
    assert "EXACTLY 3 bullets for role index 1" in d
    assert "EXACTLY 2 bullets for role index 2" in d
    assert "9 bullets total" in d


def test_build_bullet_budget_directive_is_deterministic():
    from src.agents.writer import build_bullet_budget_directive
    assert build_bullet_budget_directive([4, 4]) == build_bullet_budget_directive([4, 4])


def test_build_bullet_budget_directive_mentions_fixed_split():
    """Must state that split is fixed and relevance governs ordering within a role."""
    from src.agents.writer import build_bullet_budget_directive
    d = build_bullet_budget_directive(None)
    assert "fixed" in d.lower()
    assert "relevance" in d.lower() or "ordering" in d.lower()


# ---------------------------------------------------------------------------
# validate_bullet_counts — pure function
# ---------------------------------------------------------------------------

from src.pipeline.schemas import RoleBullets, WriterOutput


def _output_with_counts(*counts: int) -> WriterOutput:
    """Build a WriterOutput with the given number of dummy bullets per role."""
    roles = [
        RoleBullets(index=i, bullets=["x" * 200] * n)
        for i, n in enumerate(counts)
    ]
    return WriterOutput(roles=roles)


def test_validate_bullet_counts_no_violations_when_matching():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(4, 4)
    assert validate_bullet_counts(output, [4, 4]) == []


def test_validate_bullet_counts_no_violations_single_role():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(3)
    assert validate_bullet_counts(output, [3]) == []


def test_validate_bullet_counts_violation_too_many():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(5, 4)
    violations = validate_bullet_counts(output, [4, 4])
    assert len(violations) == 1
    assert "Role 0" in violations[0]
    assert "5" in violations[0]
    assert "expected EXACTLY 4" in violations[0]


def test_validate_bullet_counts_violation_too_few():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(4, 3)
    violations = validate_bullet_counts(output, [4, 4])
    assert len(violations) == 1
    assert "Role 1" in violations[0]
    assert "3" in violations[0]
    assert "expected EXACTLY 4" in violations[0]


def test_validate_bullet_counts_both_roles_wrong():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(3, 5)
    violations = validate_bullet_counts(output, [4, 4])
    assert len(violations) == 2


def test_validate_bullet_counts_none_uses_default_four_four():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(4, 4)
    assert validate_bullet_counts(output, None) == []


def test_validate_bullet_counts_none_detects_mismatch():
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(3, 4)
    violations = validate_bullet_counts(output, None)
    assert len(violations) == 1
    assert "Role 0" in violations[0]


def test_validate_bullet_counts_ignores_extra_roles_beyond_spec():
    """Writer emitted 3 roles but spec only covers 2 → only first 2 validated."""
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(4, 4, 2)  # 3 roles
    assert validate_bullet_counts(output, [4, 4]) == []


def test_validate_bullet_counts_empty_output_no_violation():
    from src.agents.validators import validate_bullet_counts
    output = WriterOutput(roles=[])
    assert validate_bullet_counts(output, [4, 4]) == []


def test_validate_bullet_counts_violation_text_contains_remove_hint():
    """Too many bullets → violation says 'Remove N'."""
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(6, 4)
    violations = validate_bullet_counts(output, [4, 4])
    assert "Remove 2" in violations[0]


def test_validate_bullet_counts_violation_text_contains_add_hint():
    """Too few bullets → violation says 'Add N'."""
    from src.agents.validators import validate_bullet_counts
    output = _output_with_counts(2, 4)
    violations = validate_bullet_counts(output, [4, 4])
    assert "Add 2" in violations[0]


# ---------------------------------------------------------------------------
# check_bullet_lengths node — count violations route through it
# ---------------------------------------------------------------------------

def test_check_bullet_lengths_detects_count_violations():
    """Node with wrong bullet count produces count_violations key."""
    from src.agents.validators import check_bullet_lengths
    output = _output_with_counts(3, 4)  # role 0 has 3, expected 4
    state = {"writer_output": output, "role_bullet_counts": [4, 4]}
    result = check_bullet_lengths(state)
    assert "count_violations" in result
    assert result["count_violations"]
    assert "Role 0" in result["count_violations"][0]


def test_check_bullet_lengths_no_count_violations_on_clean_pass():
    """Correct counts → count_violations is None in the return."""
    from src.agents.validators import check_bullet_lengths
    output = _output_with_counts(4, 4)
    state = {"writer_output": output, "role_bullet_counts": [4, 4]}
    result = check_bullet_lengths(state)
    assert result.get("count_violations") is None


def test_check_bullet_lengths_uses_default_when_no_counts_in_state():
    """No role_bullet_counts in state → defaults to [4, 4]."""
    from src.agents.validators import check_bullet_lengths
    output = _output_with_counts(4, 4)
    state = {"writer_output": output}
    result = check_bullet_lengths(state)
    assert result.get("count_violations") is None


def test_check_bullet_lengths_count_violations_does_not_affect_length_retries():
    """A count violation alone must not bump length_retries — it's a separate counter."""
    from src.agents.validators import check_bullet_lengths
    output = _output_with_counts(3, 4)
    state = {"writer_output": output, "role_bullet_counts": [4, 4]}
    result = check_bullet_lengths(state)
    # count_violations must be present but length_retries must not be bumped
    assert "count_violations" in result
    assert "length_retries" not in result


# ---------------------------------------------------------------------------
# PipelineState — role_bullet_counts channel
# ---------------------------------------------------------------------------

def test_pipeline_state_accepts_role_bullet_counts_list():
    from src.pipeline.state import PipelineState
    state: PipelineState = {"role_bullet_counts": [3, 4]}
    assert state.get("role_bullet_counts") == [3, 4]


def test_pipeline_state_accepts_role_bullet_counts_none():
    from src.pipeline.state import PipelineState
    state: PipelineState = {"role_bullet_counts": None}
    assert state.get("role_bullet_counts") is None


def test_pipeline_state_role_bullet_counts_absent_returns_none():
    from src.pipeline.state import PipelineState
    state: PipelineState = {}
    assert state.get("role_bullet_counts") is None


def test_pipeline_state_role_bullet_counts_in_annotations():
    """role_bullet_counts must be declared in PipelineState for LangGraph to track it."""
    from src.pipeline.state import PipelineState
    assert "role_bullet_counts" in PipelineState.__annotations__


# ---------------------------------------------------------------------------
# WRITER_SYSTEM — hardcoded counts removed, per-run pointer added
# ---------------------------------------------------------------------------

def test_writer_system_has_no_hardcoded_four_four():
    from src.prompts.writer import WRITER_SYSTEM
    assert "EXACTLY 4 bullets for role index 0" not in WRITER_SYSTEM
    assert "EXACTLY 4 bullets for role index 1" not in WRITER_SYSTEM
    assert "8 bullets total" not in WRITER_SYSTEM


def test_writer_system_references_per_run_bullet_budget():
    from src.prompts.writer import WRITER_SYSTEM
    assert "BULLET BUDGET" in WRITER_SYSTEM


def test_writer_system_rule7_still_present():
    """Rule 7 header must survive; only the hardcoded digits are replaced."""
    from src.prompts.writer import WRITER_SYSTEM
    assert "7. BULLET BUDGET" in WRITER_SYSTEM


# ---------------------------------------------------------------------------
# build_writer_user_message — ## BULLET BUDGET section injected
# ---------------------------------------------------------------------------

from src.pipeline.schemas import (
    JDVector,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    SkillWeight,
)


def _base_state() -> dict:
    return {
        "resume_struct": ResumeStruct(
            roles=[
                ResumeRole(company="Acme", title="SWE", start="2022", end="2024",
                           source_evidence=["Built APIs"]),
            ],
            education=["BS CS"],
            skills=["Python"],
        ),
        "jd_vector": JDVector(
            weighted_skills=[SkillWeight(name="Python", weight=0.9)],
            ats_keywords=["Python"],
            seniority="mid",
            must_mirror=["Python"],
        ),
        "gap_targets": [],
    }


def test_build_writer_user_message_contains_bullet_budget_section():
    from src.agents.writer import build_writer_user_message
    msg = build_writer_user_message(_base_state())
    assert "## BULLET BUDGET" in msg


def test_build_writer_user_message_default_counts_in_message():
    from src.agents.writer import build_writer_user_message
    msg = build_writer_user_message(_base_state())
    assert "EXACTLY 4 bullets for role index 0" in msg
    assert "EXACTLY 4 bullets for role index 1" in msg
    assert "8 bullets total" in msg


def test_build_writer_user_message_custom_counts_injected():
    from src.agents.writer import build_writer_user_message
    state = _base_state()
    state["role_bullet_counts"] = [3, 2]
    msg = build_writer_user_message(state)
    assert "EXACTLY 3 bullets for role index 0" in msg
    assert "EXACTLY 2 bullets for role index 1" in msg
    assert "5 bullets total" in msg


def test_build_writer_user_message_bullet_budget_appears_before_resume():
    from src.agents.writer import build_writer_user_message
    msg = build_writer_user_message(_base_state())
    assert msg.index("## BULLET BUDGET") < msg.index("## RESUME")


# ---------------------------------------------------------------------------
# Web schema — role_bullet_counts field on JobSubmitRequest
# ---------------------------------------------------------------------------

def test_role_bullet_counts_absent_defaults_to_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j")
    assert r.role_bullet_counts is None


def test_role_bullet_counts_valid_two_roles():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=[4, 3])
    assert r.role_bullet_counts == [4, 3]


def test_role_bullet_counts_rejects_count_below_2():
    from src.web.schemas import JobSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=[1, 4])


def test_role_bullet_counts_rejects_count_above_5():
    from src.web.schemas import JobSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=[4, 6])


def test_role_bullet_counts_rejects_empty_list():
    from src.web.schemas import JobSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=[])


def test_role_bullet_counts_accepts_boundary_values():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=[2, 5])
    assert r.role_bullet_counts == [2, 5]


def test_role_bullet_counts_explicit_none_stays_none():
    from src.web.schemas import JobSubmitRequest
    r = JobSubmitRequest(label="X", resume_tex="t", jd_text="j", role_bullet_counts=None)
    assert r.role_bullet_counts is None
