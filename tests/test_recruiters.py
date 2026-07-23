"""Tests for src.agents.recruiters — the four-persona concurrent panel.

``score_one`` is mocked so the panel returns canned ``PanelScore`` instances;
NO live API calls (ANTHROPIC_API_KEY is intentionally unset). These tests pin:

- ``recruiter_panel`` returns exactly four scores with the four distinct
  persona names;
- the Skeptic's user message includes ``source_evidence`` (it sees
  ``resume_struct``) while the ATS Matcher's does not;
- the node never mutates input state.
"""
import pytest

from src.agents import recruiters
from src.pipeline.schemas import (
    JDVector,
    PanelScore,
    ResumeRole,
    ResumeStruct,
    SkillWeight,
)


def _resume_struct() -> ResumeStruct:
    return ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp",
                title="Senior Data Engineer",
                start="Jan 2021",
                end="Present",
                source_evidence=[
                    "Built REST-based CRM-sync ETL job moving 2M records/day.",
                ],
            ),
        ],
        education=["BS Computer Science, State University, 2018"],
        skills=["Python", "SQL", "REST APIs"],
    )


def _jd_vector() -> JDVector:
    return JDVector(
        weighted_skills=[SkillWeight(name="Salesforce", weight=0.95)],
        ats_keywords=["Salesforce", "CRM"],
        seniority="senior",
        must_mirror=["Salesforce/CRM data sync"],
    )


def _state() -> dict:
    return {
        "latex_rendered": r"\documentclass{article}\begin{document}"
        r"Integrated CRM data via REST APIs.\end{document}",
        "jd_vector": _jd_vector(),
        "resume_struct": _resume_struct(),
    }


def _canned(persona: str) -> PanelScore:
    return PanelScore(
        persona=persona,
        keyword_match=80,
        impact_quality=80,
        coherence=80,
        plausibility=80,
        formatting=80,
        notes=f"{persona} note",
    )


def test_personas_registry_has_four_distinct_personas():
    assert len(recruiters.PERSONAS) == 4
    # Skeptic is the only persona flagged to receive the source struct.
    needs_source = {n for n, (_sys, needs) in recruiters.PERSONAS.items() if needs}
    assert len(needs_source) == 1


def test_recruiter_panel_returns_four_distinct_scores(monkeypatch):
    async def fake_score_one(persona_name, system, user):
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    out = recruiters.recruiter_panel(_state())

    assert set(out.keys()) == {"panel_scores"}
    scores = out["panel_scores"]
    assert len(scores) == 4
    assert all(isinstance(s, PanelScore) for s in scores)
    # Four distinct persona names.
    assert len({s.persona for s in scores}) == 4


def test_skeptic_sees_source_evidence_but_ats_does_not(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    recruiters.recruiter_panel(_state())

    # Identify the two personas by their needs_source_struct flag.
    skeptic_name = next(
        n for n, (_s, needs) in recruiters.PERSONAS.items() if needs
    )
    ats_name = next(
        n for n, (_s, needs) in recruiters.PERSONAS.items() if not needs
    )

    evidence = "Built REST-based CRM-sync ETL job moving 2M records/day."
    # Skeptic's message carries the source evidence.
    assert evidence in captured[skeptic_name]
    # A non-source persona's message does NOT carry the source evidence.
    assert evidence not in captured[ats_name]


@pytest.mark.asyncio
async def test_score_one_wraps_parse_strong_in_thread(monkeypatch):
    """score_one returns the PanelScore from parse_strong, run off-thread."""
    canned = _canned("ATS Matcher")

    def fake_parse_strong(system, user, schema, **kwargs):
        assert schema is PanelScore
        return canned

    monkeypatch.setattr(recruiters, "parse_strong", fake_parse_strong)

    result = await recruiters.score_one("ATS Matcher", "sys", "user")
    # model_copy returns a new object; check equality and that persona is canonical.
    assert result == canned
    assert result.persona == "ATS Matcher"


def test_recruiter_panel_does_not_mutate_input_state(monkeypatch):
    async def fake_score_one(persona_name, system, user):
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    state = _state()
    snapshot_keys = set(state.keys())
    recruiters.recruiter_panel(state)
    assert set(state.keys()) == snapshot_keys
    assert "panel_scores" not in state
