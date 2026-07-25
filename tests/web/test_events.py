"""Phase 8 - stream-delta → ProgressEvent translation + pct heuristic."""
from src.pipeline.schemas import PanelScore


def test_stage_detected_from_key():
    from src.web.events import build_progress_event, STAGE_LABELS
    ev = build_progress_event("job1", {"jd_vector": object()}, {"iteration": 1})
    assert ev is not None
    assert ev.stage == "analyze_jd"
    assert ev.human_label == STAGE_LABELS["analyze_jd"]


def test_unknown_delta_returns_none():
    from src.web.events import build_progress_event
    # length_violations is written by check_bullet_lengths - not in _KEY_TO_NODE
    assert build_progress_event("j", {"length_violations": []}, {}) is None


def test_no_persona_scores_without_panel_scores():
    from src.web.events import build_progress_event
    ev = build_progress_event("j", {"latex_rendered": "x"}, {"iteration": 1})
    assert ev.stage == "render"
    assert ev.persona_scores is None


def test_persona_scores_serialized_when_present():
    from src.web.events import build_progress_event
    ps = [
        PanelScore(persona=p, keyword_match=80, impact_quality=70,
                   coherence=75, plausibility=68, formatting=72, notes="n")
        for p in ("ATS Matcher", "Hiring Manager", "Technical Screener", "Skeptic")
    ]
    ev = build_progress_event("j", {"panel_scores": ps}, {"iteration": 2})
    assert ev.stage == "recruiter_panel"
    assert ev.persona_scores is not None and len(ev.persona_scores) == 4
    first = ev.persona_scores[0]
    assert first.persona == "ATS Matcher"
    assert first.keyword_match == 80
    assert first.notes == "n"


def test_writer_label_includes_iteration():
    from src.web.events import build_progress_event
    ev = build_progress_event("j", {"writer_output": object()}, {"iteration": 3})
    assert ev.stage == "writer"
    assert "3" in ev.human_label


def test_event_carries_aggregate_and_passed_from_state():
    from src.web.events import build_progress_event
    ev = build_progress_event(
        "j", {"aggregate_score": 81.5}, {"iteration": 2, "aggregate_score": 81.5, "passed": True}
    )
    assert ev.stage == "aggregator"
    assert ev.aggregate_score == 81.5
    assert ev.passed is True


def test_pct_estimate_monotonic_across_writer_loop():
    from src.web.events import pct_estimate
    seq = [
        ("parse_resume", 1), ("analyze_jd", 1), ("gap_analysis", 1), ("generate_skills", 1),
        ("writer", 1), ("compile", 1), ("recruiter_panel", 1), ("aggregator", 1), ("bookkeep", 1),
        ("writer", 2), ("compile", 2),
        ("emit", 2),
    ]
    pcts = [pct_estimate(s, i) for s, i in seq]
    assert pcts == sorted(pcts), pcts
    assert pcts[0] >= 0 and pcts[-1] <= 100


def test_pct_estimate_honours_max_iterations_budget():
    from src.web.events import pct_estimate

    # A larger loop budget spreads the 25–90% band across more iterations, so the
    # same (stage, iteration) reads a lower pct than under the default budget.
    default_pct = pct_estimate("writer", 2, 4)
    roomy_pct = pct_estimate("writer", 2, 8)
    assert roomy_pct < default_pct
    # Still monotonic across iterations under the tuned budget.
    assert pct_estimate("writer", 2, 8) <= pct_estimate("writer", 3, 8)


def test_pct_estimate_zero_budget_does_not_crash():
    from src.web.events import pct_estimate

    assert 0 <= pct_estimate("writer", 1, 0) <= 100
