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

    assert set(out.keys()) == {"panel_scores", "panel_cache_latex", "panel_cache_scores"}
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
async def test_score_one_wraps_parse_scoring_in_thread(monkeypatch):
    """score_one returns the PanelScore from parse_scoring, run off-thread."""
    canned = _canned("ATS Matcher")

    def fake_parse_scoring(system, user, schema, **kwargs):
        assert schema is PanelScore
        return canned

    monkeypatch.setattr(recruiters, "parse_scoring", fake_parse_scoring)

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


# --- exact-match panel-score cache (Tier 3 cost optimization) -----------------


def test_recruiter_panel_reuses_cached_scores_when_latex_unchanged(monkeypatch):
    """When latex_rendered is byte-identical to panel_cache_latex (the writer
    produced the same draft as last time it was scored), the panel must NOT
    re-run any persona call — it reuses panel_cache_scores verbatim."""
    call_count = {"n": 0}

    async def fake_score_one(persona_name, system, user):
        call_count["n"] += 1
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    cached_scores = [_canned(name) for name in recruiters.PERSONAS]
    state = _state()
    state["panel_cache_latex"] = state["latex_rendered"]
    state["panel_cache_scores"] = cached_scores

    out = recruiters.recruiter_panel(state)

    assert call_count["n"] == 0, "cache hit must skip every persona call"
    assert out["panel_scores"] == cached_scores
    assert out["panel_cache_latex"] == state["latex_rendered"]
    assert out["panel_cache_scores"] == cached_scores


def test_recruiter_panel_runs_and_updates_cache_when_latex_changes(monkeypatch):
    """A different latex_rendered than what's cached is a cache MISS — the
    panel runs normally and the cache is refreshed to the new draft/scores."""
    call_count = {"n": 0}

    async def fake_score_one(persona_name, system, user):
        call_count["n"] += 1
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    state = _state()
    state["panel_cache_latex"] = "SOME OLDER DRAFT"
    state["panel_cache_scores"] = [_canned(name) for name in recruiters.PERSONAS]

    out = recruiters.recruiter_panel(state)

    assert call_count["n"] == 4, "cache miss must run all four persona calls"
    assert out["panel_cache_latex"] == state["latex_rendered"]
    assert out["panel_cache_scores"] == out["panel_scores"]


def test_recruiter_panel_first_call_has_no_cache_and_runs_normally(monkeypatch):
    """No panel_cache_latex/panel_cache_scores present (first-ever scoring
    pass) must behave exactly like a cache miss, not raise or skip."""
    call_count = {"n": 0}

    async def fake_score_one(persona_name, system, user):
        call_count["n"] += 1
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    out = recruiters.recruiter_panel(_state())

    assert call_count["n"] == 4
    assert out["panel_cache_latex"] == _state()["latex_rendered"]
