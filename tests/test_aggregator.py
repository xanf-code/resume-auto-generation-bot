"""Tests for src.agents.aggregator - pure-code scoring + plausibility floor.

The scoring math is pure and needs NO mocks. The single LLM call
(``distill_revision_notes``) is mocked to return a canned ``RevisionNotes``;
NO live API calls (ANTHROPIC_API_KEY is intentionally unset).

Key guarantees pinned here:
- weighted-mean composite math is exact on a hand-computed example;
- ``aggregate`` is the exact mean of the four persona composites;
- the plausibility FLOOR forces a FAIL even when ``aggregate`` >= 88
  (the fabrication guard);
- PASS requires BOTH ``aggregate`` >= 88 AND skeptic plausibility >= 70;
- the aggregator node calls the LLM ONLY on the fail path (never on pass) and
  never mutates input state.
"""
import dataclasses

import pytest

from src.agents import aggregator
from src.pipeline.schemas import PanelScore, RevisionNotes
from src.pipeline.tuning import PipelineTuning


def _score(persona: str, *, km, iq, coh, plaus, fmt, notes="note") -> PanelScore:
    return PanelScore(
        persona=persona,
        keyword_match=km,
        impact_quality=iq,
        coherence=coh,
        plausibility=plaus,
        formatting=fmt,
        notes=notes,
    )


# --- persona_composite: exact weighted-mean math ------------------------------


def test_persona_composite_exact_weighted_mean():
    """Weights: km .30, iq .20, coh .20, plaus .15, fmt .15 - hand-computed."""
    s = _score("ATS Matcher", km=80, iq=70, coh=60, plaus=90, fmt=100)
    # 0.30*80 + 0.20*70 + 0.20*60 + 0.15*90 + 0.15*100
    # = 24 + 14 + 12 + 13.5 + 15 = 78.5
    assert aggregator.persona_composite(s) == pytest.approx(78.5)


def test_persona_composite_all_equal_returns_that_value():
    """When every dimension equals v, the weighted mean is v (weights sum to 1)."""
    s = _score("Hiring Manager", km=88, iq=88, coh=88, plaus=88, fmt=88)
    assert aggregator.persona_composite(s) == pytest.approx(88.0)


# --- aggregate: exact mean of four composites ---------------------------------


def test_aggregate_is_mean_of_four_composites():
    scores = [
        _score("ATS Matcher", km=90, iq=90, coh=90, plaus=90, fmt=90),  # 90
        _score("Hiring Manager", km=80, iq=80, coh=80, plaus=80, fmt=80),  # 80
        _score("Technical Screener", km=70, iq=70, coh=70, plaus=70, fmt=70),  # 70
        _score("Skeptic", km=100, iq=100, coh=100, plaus=100, fmt=100),  # 100
    ]
    # mean(90, 80, 70, 100) = 85.0
    assert aggregator.aggregate(scores) == pytest.approx(85.0)


def test_skeptic_plausibility_reads_the_skeptic():
    scores = [
        _score("ATS Matcher", km=90, iq=90, coh=90, plaus=95, fmt=90),
        _score("Hiring Manager", km=90, iq=90, coh=90, plaus=95, fmt=90),
        _score("Technical Screener", km=90, iq=90, coh=90, plaus=95, fmt=90),
        _score("Skeptic", km=90, iq=90, coh=90, plaus=42, fmt=90),
    ]
    assert aggregator.skeptic_plausibility(scores) == 42


# --- decide: plausibility floor is the fabrication guard ----------------------


def test_plausibility_floor_forces_fail_even_when_aggregate_high():
    """Aggregate >= 88 but skeptic plausibility < 20 => FAIL. Fabrication guard."""
    # Every persona scores high on everything, so aggregate is well above 88,
    # EXCEPT the skeptic's plausibility, which sits below the floor of 20.
    scores = [
        _score("ATS Matcher", km=95, iq=95, coh=95, plaus=95, fmt=95),
        _score("Hiring Manager", km=95, iq=95, coh=95, plaus=95, fmt=95),
        _score("Technical Screener", km=95, iq=95, coh=95, plaus=95, fmt=95),
        # Skeptic: everything high but plausibility 10 (< floor 20).
        _score("Skeptic", km=95, iq=95, coh=95, plaus=10, fmt=95),
    ]
    passed, agg = aggregator.decide(scores)

    assert agg >= 88, "sanity: aggregate must be >= threshold for this guard test"
    assert passed is False, "floor must veto a high aggregate when plausibility < 20"


def test_pass_requires_both_aggregate_and_floor():
    """PASS only when aggregate >= 88 AND skeptic plausibility >= 70."""
    scores = [
        _score("ATS Matcher", km=90, iq=90, coh=90, plaus=90, fmt=90),
        _score("Hiring Manager", km=90, iq=90, coh=90, plaus=90, fmt=90),
        _score("Technical Screener", km=90, iq=90, coh=90, plaus=90, fmt=90),
        _score("Skeptic", km=90, iq=90, coh=90, plaus=90, fmt=90),
    ]
    passed, agg = aggregator.decide(scores)
    assert agg >= 88
    assert passed is True


def test_fail_when_aggregate_below_threshold_even_if_floor_holds():
    """Low aggregate fails even though skeptic plausibility clears the floor."""
    scores = [
        _score("ATS Matcher", km=70, iq=70, coh=70, plaus=75, fmt=70),
        _score("Hiring Manager", km=70, iq=70, coh=70, plaus=75, fmt=70),
        _score("Technical Screener", km=70, iq=70, coh=70, plaus=75, fmt=70),
        _score("Skeptic", km=70, iq=70, coh=70, plaus=75, fmt=70),
    ]
    passed, agg = aggregator.decide(scores)
    assert agg < 88
    assert passed is False


# --- distill_revision_notes + aggregator node ---------------------------------


def _failing_scores() -> list[PanelScore]:
    return [
        _score("ATS Matcher", km=60, iq=60, coh=60, plaus=65, fmt=60,
               notes="Missing keyword: Kubernetes."),
        _score("Hiring Manager", km=60, iq=60, coh=60, plaus=65, fmt=60,
               notes="Impact bullets lack outcomes."),
        _score("Technical Screener", km=60, iq=60, coh=60, plaus=65, fmt=60,
               notes="Stack depth unclear."),
        _score("Skeptic", km=60, iq=60, coh=60, plaus=50, fmt=60,
               notes="Bullet 2 overstates scope; no source for 'Salesforce'."),
    ]


def _passing_scores() -> list[PanelScore]:
    return [
        _score("ATS Matcher", km=92, iq=92, coh=92, plaus=92, fmt=92),
        _score("Hiring Manager", km=92, iq=92, coh=92, plaus=92, fmt=92),
        _score("Technical Screener", km=92, iq=92, coh=92, plaus=92, fmt=92),
        _score("Skeptic", km=90, iq=90, coh=90, plaus=90, fmt=90),
    ]


def test_distill_revision_notes_mocks_llm_and_returns_list(monkeypatch):
    canned = RevisionNotes(notes=["1. Add Kubernetes.", "2. Quantify impact."])
    captured = {}

    def fake_parse_scoring(system, user, schema, **kwargs):
        captured["schema"] = schema
        captured["user"] = user
        return canned

    monkeypatch.setattr(aggregator, "parse_scoring", fake_parse_scoring)

    notes = aggregator.distill_revision_notes(_failing_scores())

    assert captured["schema"] is RevisionNotes
    assert notes == ["1. Add Kubernetes.", "2. Quantify impact."]
    # The persona notes are fed into the distillation prompt.
    assert "Salesforce" in captured["user"]


def test_aggregator_fail_path_writes_revision_notes(monkeypatch):
    canned = RevisionNotes(notes=["1. Source or remove the Salesforce claim."])
    called = {"n": 0}

    def fake_parse_scoring(system, user, schema, **kwargs):
        called["n"] += 1
        return canned

    monkeypatch.setattr(aggregator, "parse_scoring", fake_parse_scoring)

    state = {"panel_scores": _failing_scores()}
    out = aggregator.aggregator(state)

    assert out["passed"] is False
    assert out["revision_notes"] == ["1. Source or remove the Salesforce claim."]
    assert "aggregate_score" in out and "panel_scores" in out
    assert called["n"] == 1, "the distillation LLM call must fire exactly once on fail"


def test_aggregator_pass_path_never_calls_llm(monkeypatch):
    called = {"n": 0}

    def fake_parse_scoring(*a, **k):
        called["n"] += 1
        raise AssertionError("LLM must NOT be called on the pass path")

    monkeypatch.setattr(aggregator, "parse_scoring", fake_parse_scoring)

    state = {"panel_scores": _passing_scores()}
    out = aggregator.aggregator(state)

    assert out["passed"] is True
    assert called["n"] == 0
    assert "revision_notes" not in out
    assert out["aggregate_score"] >= 88


def test_aggregator_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(
        aggregator, "parse_scoring",
        lambda *a, **k: RevisionNotes(notes=["x"]),
    )
    state = {"panel_scores": _failing_scores()}
    snapshot_keys = set(state.keys())
    aggregator.aggregator(state)
    assert set(state.keys()) == snapshot_keys
    assert "passed" not in state


# --- per-run tuning: custom weights / threshold / floor -----------------------


def test_persona_composite_honours_custom_weights():
    """All weight on keyword_match => composite equals keyword_match."""
    s = _score("ATS Matcher", km=42, iq=99, coh=99, plaus=99, fmt=99)
    weights = {
        "keyword_match": 1.0,
        "impact_quality": 0.0,
        "coherence": 0.0,
        "plausibility": 0.0,
        "formatting": 0.0,
    }
    assert aggregator.persona_composite(s, weights=weights) == pytest.approx(42.0)


def test_aggregate_honours_custom_weights():
    scores = [
        _score("ATS Matcher", km=40, iq=80, coh=80, plaus=80, fmt=80),
        _score("Skeptic", km=60, iq=80, coh=80, plaus=80, fmt=80),
    ]
    weights = {
        "keyword_match": 1.0,
        "impact_quality": 0.0,
        "coherence": 0.0,
        "plausibility": 0.0,
        "formatting": 0.0,
    }
    # composites collapse to km => mean(40, 60) = 50
    assert aggregator.aggregate(scores, weights=weights) == pytest.approx(50.0)


def test_decide_custom_threshold_flips_verdict():
    """An 85-aggregate draft passes at threshold 78 but fails at 90."""
    scores = [
        _score("ATS Matcher", km=85, iq=85, coh=85, plaus=85, fmt=85),
        _score("Hiring Manager", km=85, iq=85, coh=85, plaus=85, fmt=85),
        _score("Technical Screener", km=85, iq=85, coh=85, plaus=85, fmt=85),
        _score("Skeptic", km=85, iq=85, coh=85, plaus=85, fmt=85),
    ]
    passed_low, agg = aggregator.decide(scores, threshold=78, floor=20)
    passed_high, _ = aggregator.decide(scores, threshold=90, floor=20)
    assert agg == pytest.approx(85.0)
    assert passed_low is True
    assert passed_high is False


def test_decide_custom_floor_vetoes():
    """Skeptic plausibility 30 clears the default floor but not a floor of 40."""
    scores = [
        _score("ATS Matcher", km=95, iq=95, coh=95, plaus=95, fmt=95),
        _score("Hiring Manager", km=95, iq=95, coh=95, plaus=95, fmt=95),
        _score("Technical Screener", km=95, iq=95, coh=95, plaus=95, fmt=95),
        _score("Skeptic", km=95, iq=95, coh=95, plaus=30, fmt=95),
    ]
    passed_low, _ = aggregator.decide(scores, threshold=78, floor=20)
    passed_high, _ = aggregator.decide(scores, threshold=78, floor=40)
    assert passed_low is True
    assert passed_high is False


def test_aggregator_node_reads_threshold_from_state_tuning(monkeypatch):
    """A draft that passes at the default threshold fails when state raises it."""
    called = {"n": 0}

    def fake_parse_scoring(system, user, schema, **kwargs):
        called["n"] += 1
        return RevisionNotes(notes=["1. Push keyword coverage higher."])

    monkeypatch.setattr(aggregator, "parse_scoring", fake_parse_scoring)

    strict = dataclasses.replace(PipelineTuning.defaults(), threshold=95)
    state = {"panel_scores": _passing_scores(), "tuning": strict}
    out = aggregator.aggregator(state)

    assert out["passed"] is False
    assert called["n"] == 1
    assert out["revision_notes"] == ["1. Push keyword coverage higher."]
