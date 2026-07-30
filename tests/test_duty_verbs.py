"""Tests for GAP 4 - anchoring fabrications to JD duty-verbs, not just keywords.

The JD Analyzer extracts `duty_verbs` (the imperative "what you will do" action
phrases from the JD) alongside its existing vocabulary extraction. The Gap
Analyzer then maps reframe targets to those duty_verbs so a fabricated bullet
reads as evidence of performing a stated duty, not just a keyword match.
"""
from src.agents.gap_analyzer import build_user_message
from src.pipeline.schemas import JDVector, ResumeRole, ResumeStruct, SkillWeight
from src.prompts.extraction import GAP_SYSTEM, JD_SYSTEM


def _resume_struct() -> ResumeStruct:
    return ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp",
                title="Senior Data Engineer",
                start="Jan 2021",
                end="Present",
                source_evidence=["Built REST-based ETL job moving 2M records/day."],
            ),
        ],
        education=["BS Computer Science, State University, 2018"],
        skills=["Python", "SQL"],
    )


def _jd_vector_with_duty_verbs() -> JDVector:
    return JDVector(
        weighted_skills=[SkillWeight(name="Observability", weight=0.8)],
        ats_keywords=["telemetry", "feature flags"],
        seniority="senior",
        must_mirror=["gradual rollouts"],
        duty_verbs=[
            "instrument services with telemetry",
            "support gradual rollouts with feature flags",
        ],
    )


# --- JD schema: duty_verbs field --------------------------------------------


def test_jd_vector_duty_verbs_defaults_to_empty_list():
    vector = JDVector(
        weighted_skills=[SkillWeight(name="Python", weight=0.9)],
        ats_keywords=["Python"],
        seniority="senior",
        must_mirror=["distributed systems"],
    )
    assert vector.duty_verbs == []


def test_jd_vector_round_trips_with_populated_duty_verbs():
    vector = _jd_vector_with_duty_verbs()
    restored = JDVector.model_validate_json(vector.model_dump_json())
    assert restored == vector
    assert restored.duty_verbs == [
        "instrument services with telemetry",
        "support gradual rollouts with feature flags",
    ]


# --- JD_SYSTEM: instructs duty_verbs extraction -----------------------------


def test_jd_system_instructs_duty_verb_extraction():
    assert "duty_verbs" in JD_SYSTEM
    lowered = JD_SYSTEM.lower()
    assert "what you will do" in lowered or "responsibilities" in lowered
    assert "0-12" in JD_SYSTEM or "0 to 12" in JD_SYSTEM.lower()


def test_jd_system_duty_verbs_kept_as_jd_phrasing():
    lowered = JD_SYSTEM.lower()
    assert "not lemmatiz" in lowered.replace("s section", "") or "do not lemmatize" in lowered


def test_jd_system_existing_produce_items_untouched():
    assert "weighted_skills" in JD_SYSTEM
    assert "ats_keywords" in JD_SYSTEM
    assert "must_mirror" in JD_SYSTEM
    assert "seniority" in JD_SYSTEM


# --- GAP_SYSTEM: directs duty-verb mapping ----------------------------------


def test_gap_system_directs_duty_verb_mapping():
    lowered = GAP_SYSTEM.lower()
    assert "duty_verb" in lowered
    assert "evidence of performing" in lowered


def test_gap_system_prefers_duty_satisfying_competency_over_keyword_only():
    lowered = GAP_SYSTEM.lower()
    assert "keyword-only" in lowered or "keyword only" in lowered
    assert "prefer" in lowered


def test_gap_system_existing_hard_rules_untouched():
    assert "host_role_index" in GAP_SYSTEM
    assert "no_evidence: ALWAYS false" in GAP_SYSTEM
    assert "NEVER use -1" in GAP_SYSTEM
    assert "non-obvious implementation detail" in GAP_SYSTEM


# --- wiring: duty_verbs reaches the Gap Analyzer's user message ------------


def test_build_user_message_includes_duty_verbs():
    msg = build_user_message(_resume_struct(), _jd_vector_with_duty_verbs())
    assert "duty_verbs" in msg
    assert "instrument services with telemetry" in msg
    assert "support gradual rollouts with feature flags" in msg
