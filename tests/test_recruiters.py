"""Tests for src.agents.recruiters - the four-persona concurrent panel.

``score_one`` is mocked so the panel returns canned ``PanelScore`` instances;
NO live API calls (ANTHROPIC_API_KEY is intentionally unset). These tests pin:

- ``recruiter_panel`` returns exactly four scores with the four distinct
  persona names;
- the Skeptic's user message includes ``source_evidence`` (it sees
  ``resume_struct``) while the ATS Matcher's does not;
- the node never mutates input state.
"""
import logging

import openai
import pytest

from src.agents import recruiters
from src.pipeline.schemas import (
    InventedTool,
    JDVector,
    PanelScore,
    ResumeRole,
    ResumeStruct,
    SkillWeight,
    WriterOutput,
    RoleBullets,
)
from src.prompts.recruiters import DISTILL_NOTES_SYSTEM, SKEPTIC_SYSTEM


def _length_finish_reason_error() -> openai.LengthFinishReasonError:
    class _Usage:
        completion_tokens = 16000
        prompt_tokens = 100
        total_tokens = 16100

    class _Completion:
        usage = _Usage()

    return openai.LengthFinishReasonError(completion=_Completion())


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


def test_recruiter_panel_logs_the_actual_model_context_override(monkeypatch, caplog):
    """Regression test: the log line used to hardcode MODEL_SCORING from
    config.settings, so it lied whenever a per-job model_context override was
    active. It must report the override, not the static settings constant."""
    from src.pipeline.llm import model_context

    async def fake_score_one(persona_name, system, user):
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    with caplog.at_level(logging.INFO, logger="src.agents.recruiters"):
        with model_context(
            fast="f",
            strong="s",
            scoring="deepseek/deepseek-v4-flash",
            effort_scoring="xhigh",
            temp_scoring=0.2,
        ):
            recruiters.recruiter_panel(_state())

    log_text = " ".join(caplog.messages)
    assert "deepseek/deepseek-v4-flash" in log_text
    assert "effort=xhigh" in log_text
    assert "temp=0.2" in log_text


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


@pytest.mark.asyncio
async def test_score_one_overrides_persona_even_when_model_omitted_it(monkeypatch):
    """Regression test for the real production crash: some providers' structured
    output can omit `persona` entirely (the prompt never asks the model to fill
    it in - see PanelScore's docstring). PanelScore.model_validate mirrors what
    the OpenAI SDK does internally when parsing the raw response; it must not
    raise, and score_one must still stamp the canonical persona name on top."""

    def fake_parse_scoring(system, user, schema, **kwargs):
        # Simulates the model's JSON response arriving with no "persona" key -
        # PanelScore.persona defaults instead of raising a ValidationError.
        return PanelScore.model_validate({
            "keyword_match": 45, "impact_quality": 50, "coherence": 60,
            "plausibility": 55, "formatting": 65, "notes": "Clean and ATS-friendly.",
        })

    monkeypatch.setattr(recruiters, "parse_scoring", fake_parse_scoring)

    result = await recruiters.score_one("Technical Screener", "sys", "user")

    assert result.persona == "Technical Screener"
    assert result.keyword_match == 45


@pytest.mark.asyncio
async def test_score_one_retries_once_on_length_error_and_succeeds(monkeypatch):
    """A single LengthFinishReasonError is retried transparently - the caller
    never sees it as long as the retry succeeds."""
    canned = _canned("Hiring Manager")
    calls = {"n": 0}

    def fake_parse_scoring(system, user, schema, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _length_finish_reason_error()
        return canned

    monkeypatch.setattr(recruiters, "parse_scoring", fake_parse_scoring)

    result = await recruiters.score_one("Hiring Manager", "sys", "user")

    assert calls["n"] == 2
    assert result.persona == "Hiring Manager"
    assert result.notes == "Hiring Manager note"


@pytest.mark.asyncio
async def test_score_one_falls_back_to_neutral_score_after_two_length_errors(monkeypatch):
    """Two consecutive LengthFinishReasonErrors must not crash the run - the
    persona gets a neutral placeholder score instead."""
    calls = {"n": 0}

    def fake_parse_scoring(system, user, schema, **kwargs):
        calls["n"] += 1
        raise _length_finish_reason_error()

    monkeypatch.setattr(recruiters, "parse_scoring", fake_parse_scoring)

    result = await recruiters.score_one("Skeptic", "sys", "user")

    assert calls["n"] == 2, "must retry exactly once before falling back"
    assert result.persona == "Skeptic"
    assert result.keyword_match == recruiters._FALLBACK_SCORE_VALUE
    assert result.plausibility == recruiters._FALLBACK_SCORE_VALUE
    assert "length limit" in result.notes


# --- invention ledger wiring (GAP 1: Skeptic sees the fabrication ledger) ----


def _writer_output_with_ledger() -> WriterOutput:
    return WriterOutput(
        roles=[RoleBullets(index=0, bullets=["Did a thing"])],
        invented_stack=[
            InventedTool(
                tool="Kafka",
                introduced_in="role 0 bullet 2",
                supporting_detail="partitioned by customer_id for ordered replay",
                reused_in=["role 1 bullet 1"],
            ),
        ],
    )


def test_skeptic_sees_invented_stack_but_ats_does_not(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    state = _state()
    state["writer_output"] = _writer_output_with_ledger()
    recruiters.recruiter_panel(state)

    skeptic_name = next(
        n for n, (_s, needs) in recruiters.PERSONAS.items() if needs
    )
    ats_name = next(
        n for n, (_s, needs) in recruiters.PERSONAS.items() if not needs
    )

    assert "partitioned by customer_id for ordered replay" in captured[skeptic_name]
    assert "partitioned by customer_id for ordered replay" not in captured[ats_name]


def test_skeptic_sees_locked_invented_stack_over_live_writer_output(monkeypatch):
    """Once ``invented_stack`` is locked in state, the panel must read the locked
    channel rather than the live (possibly-thinned) writer_output copy."""
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    locked_ledger = [
        InventedTool(
            tool="Kafka",
            introduced_in="role 0 bullet 2",
            supporting_detail="partitioned by customer_id for ordered replay",
            reused_in=["role 1 bullet 1"],
        ),
    ]
    thinned_writer_output = WriterOutput(
        roles=[RoleBullets(index=0, bullets=["Did a thing"])],
        invented_stack=[],
    )

    state = _state()
    state["invented_stack"] = locked_ledger
    state["writer_output"] = thinned_writer_output
    recruiters.recruiter_panel(state)

    skeptic_name = next(n for n, (_s, needs) in recruiters.PERSONAS.items() if needs)
    assert "partitioned by customer_id for ordered replay" in captured[skeptic_name]


def test_skeptic_falls_back_to_live_writer_output_when_not_yet_locked(monkeypatch):
    """Before the first-pass lock fires, the panel must still see the live
    writer_output ledger (first-iteration scoring, pre-lock)."""
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    state = _state()
    state["writer_output"] = _writer_output_with_ledger()
    recruiters.recruiter_panel(state)

    skeptic_name = next(n for n, (_s, needs) in recruiters.PERSONAS.items() if needs)
    assert "partitioned by customer_id for ordered replay" in captured[skeptic_name]


def test_recruiter_panel_handles_missing_writer_output(monkeypatch):
    """No writer_output in state (e.g. pre-writer scoring) must not crash."""
    async def fake_score_one(persona_name, system, user):
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    out = recruiters.recruiter_panel(_state())
    assert len(out["panel_scores"]) == 4


def test_skeptic_system_documents_cross_bullet_coherence():
    assert "invented_stack" in SKEPTIC_SYSTEM
    assert "CROSS-BULLET COHERENCE" in SKEPTIC_SYSTEM
    assert "below 30" in SKEPTIC_SYSTEM.lower() or "BELOW 30" in SKEPTIC_SYSTEM
    # Existing plausibility scoring stance must remain intact.
    assert "50-70" in SKEPTIC_SYSTEM


# --- Skeptic repair-engine upgrade (GAP 6: notes carry reason + repair) ------


def test_skeptic_system_requires_reason_and_repair_pair():
    """Every flagged bullet must carry BOTH why it fails AND the minimal fix."""
    lowered = SKEPTIC_SYSTEM.lower()
    assert "repair" in lowered
    # The three sanctioned repair moves must all be named.
    assert "corroborating detail" in lowered
    assert "downgrade" in lowered
    assert "cut" in lowered


def test_skeptic_system_has_worked_repair_example():
    """A concrete worked example anchors the reason+repair shape for the model."""
    assert "Kafka" in SKEPTIC_SYSTEM
    assert "REPAIR:" in SKEPTIC_SYSTEM
    assert "message-queue-based async processing" in SKEPTIC_SYSTEM


def test_skeptic_system_scoring_stance_unchanged_by_repair_upgrade():
    """The note SHAPE changes, but the score scale must not."""
    assert "50-70" in SKEPTIC_SYSTEM
    assert "below 30" in SKEPTIC_SYSTEM.lower()


def test_distill_notes_system_preserves_repair_as_imperative():
    """Distilled directives must keep the Skeptic's concrete fix, not flatten it
    to a generic 'make it more plausible' instruction."""
    lowered = DISTILL_NOTES_SYSTEM.lower()
    assert "repair" in lowered
    assert "preserve" in lowered


def test_distill_notes_system_ranking_rules_unchanged():
    """Existing ranking rules (plausibility weight, Skeptic traceability
    outranking cosmetics) must survive the repair-preservation upgrade."""
    assert "0.30" in DISTILL_NOTES_SYSTEM
    assert "traceability" in DISTILL_NOTES_SYSTEM.lower()
    assert "cosmetic" in DISTILL_NOTES_SYSTEM.lower()


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
    re-run any persona call - it reuses panel_cache_scores verbatim."""
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
    """A different latex_rendered than what's cached is a cache MISS - the
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


# --- FABRICATION ENVELOPE wiring (GAP 5: Skeptic scores against the same
# envelope the Writer was given) ------------------------------------------------


def test_skeptic_sees_fabrication_envelope_but_ats_does_not(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    state = _state()
    state["jd_domains"] = ["realtime", "microservices"]
    recruiters.recruiter_panel(state)

    skeptic_name = next(n for n, (_s, needs) in recruiters.PERSONAS.items() if needs)
    ats_name = next(n for n, (_s, needs) in recruiters.PERSONAS.items() if not needs)

    assert "## FABRICATION ENVELOPE" in captured[skeptic_name]
    assert "Kafka" in captured[skeptic_name]
    assert "## FABRICATION ENVELOPE" not in captured[ats_name]


def test_skeptic_fabrication_envelope_empty_when_no_jd_domains(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_score_one(persona_name, system, user):
        captured[persona_name] = user
        return _canned(persona_name)

    monkeypatch.setattr(recruiters, "score_one", fake_score_one)

    recruiters.recruiter_panel(_state())

    skeptic_name = next(n for n, (_s, needs) in recruiters.PERSONAS.items() if needs)
    assert "## FABRICATION ENVELOPE" in captured[skeptic_name]


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
