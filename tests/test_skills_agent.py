"""Tests for src.agents.skills — the one-shot skill dump generator.

``parse_skills`` is mocked; NO live API calls. Tests pin:
- build_skills_user_message includes resume skills, JD vector, and gap competencies.
- generate_skills calls parse_skills once and stores the dump.
- Idempotency: skill_dump already present → no call, returns {}.
- Graceful failure: parse_skills raises → empty SkillDump returned, no exception.
"""
from src.agents import skills as skills_mod
from src.pipeline.schemas import (
    JDVector,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    SkillDump,
    SkillWeight,
)


def _resume_struct() -> ResumeStruct:
    return ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp",
                title="Engineer",
                start="2021",
                end="Present",
                source_evidence=["Built REST pipeline."],
            ),
        ],
        education=["BS Computer Science"],
        skills=["Python", "SQL", "REST APIs"],
    )


def _jd_vector() -> JDVector:
    return JDVector(
        weighted_skills=[
            SkillWeight(name="Salesforce", weight=0.95),
            SkillWeight(name="Kubernetes", weight=0.6),
        ],
        ats_keywords=["Salesforce", "CRM", "Kubernetes"],
        seniority="senior",
        must_mirror=["Salesforce/CRM data sync"],
    )


def _gap_targets() -> list[ReframingTarget]:
    return [
        ReframingTarget(
            competency="Salesforce",
            weight=0.95,
            host_role_index=0,
            real_evidence=["Built REST CRM-sync ETL."],
            framing_guidance="Frame as CRM integration.",
            no_evidence=False,
        ),
        ReframingTarget(
            competency="Kubernetes",
            weight=0.6,
            host_role_index=0,
            real_evidence=[],
            framing_guidance="",
            no_evidence=True,  # should NOT appear in message
        ),
    ]


def _first_iteration_state() -> dict:
    return {
        "resume_struct": _resume_struct(),
        "jd_vector": _jd_vector(),
        "gap_targets": _gap_targets(),
    }


# --- build_skills_user_message ------------------------------------------------


def test_message_includes_resume_skills():
    msg = skills_mod.build_skills_user_message(
        _resume_struct(), _jd_vector(), _gap_targets()
    )
    assert "Python" in msg
    assert "SQL" in msg
    assert "REST APIs" in msg


def test_message_includes_jd_vector():
    msg = skills_mod.build_skills_user_message(
        _resume_struct(), _jd_vector(), _gap_targets()
    )
    # JD vector is serialized as JSON; its keys should appear.
    assert "weighted_skills" in msg
    assert "ats_keywords" in msg
    assert "Salesforce" in msg


def test_message_includes_active_gap_competencies():
    """Gap competencies with no_evidence=False appear; no_evidence=True are omitted."""
    msg = skills_mod.build_skills_user_message(
        _resume_struct(), _jd_vector(), _gap_targets()
    )
    assert "Salesforce" in msg      # no_evidence=False — active
    assert "Kubernetes" not in msg.split("GAP-REFRAME")[1].split("\n")[1]  # no_evidence=True


def test_message_handles_empty_gap_targets():
    msg = skills_mod.build_skills_user_message(_resume_struct(), _jd_vector(), [])
    assert "(none)" in msg


# --- generate_skills node -----------------------------------------------------


def test_generate_skills_calls_parse_skills_once(monkeypatch):
    """generate_skills fires parse_skills exactly once and stores the result."""
    canned = SkillDump(
        language_and_framework=["Python"],
        infrastructure=["AWS"],
        database=[],
        ai_tools=[],
    )
    calls = {"n": 0}

    def fake_parse(system, user, schema, **kwargs):
        calls["n"] += 1
        return canned

    monkeypatch.setattr(skills_mod, "parse_skills", fake_parse)

    result = skills_mod.generate_skills(_first_iteration_state())

    assert calls["n"] == 1
    assert "skill_dump" in result
    assert result["skill_dump"] is canned


def test_generate_skills_idempotent_when_dump_already_present(monkeypatch):
    """If skill_dump is already a SkillDump, returns {} — no parse_skills call."""
    existing = SkillDump(language_and_framework=["Go"])
    called = {"called": False}

    def fake_parse(*args, **kwargs):
        called["called"] = True
        return SkillDump()

    monkeypatch.setattr(skills_mod, "parse_skills", fake_parse)

    state = {**_first_iteration_state(), "skill_dump": existing}
    result = skills_mod.generate_skills(state)

    assert result == {}
    assert called["called"] is False


def test_generate_skills_graceful_on_failure(monkeypatch):
    """If parse_skills raises, returns an empty SkillDump — no exception escapes."""
    def boom(*args, **kwargs):
        raise RuntimeError("API call failed")

    monkeypatch.setattr(skills_mod, "parse_skills", boom)

    result = skills_mod.generate_skills(_first_iteration_state())

    assert "skill_dump" in result
    assert isinstance(result["skill_dump"], SkillDump)
    assert result["skill_dump"].total() == 0


def test_generate_skills_returns_only_skill_dump_key(monkeypatch):
    """Node contract: returns exactly {'skill_dump': <dump>} on success."""
    monkeypatch.setattr(skills_mod, "parse_skills", lambda *a, **k: SkillDump())

    result = skills_mod.generate_skills(_first_iteration_state())

    assert set(result.keys()) == {"skill_dump"}


def test_generate_skills_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(skills_mod, "parse_skills", lambda *a, **k: SkillDump())

    state = _first_iteration_state()
    snapshot = set(state.keys())
    skills_mod.generate_skills(state)

    assert set(state.keys()) == snapshot
    assert "skill_dump" not in state
