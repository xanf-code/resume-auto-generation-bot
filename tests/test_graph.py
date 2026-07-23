"""Tests for src.pipeline.graph — the LangGraph wiring, routing, and bookkeeping.

ALL node/LLM behaviour is mocked. NO live API calls (ANTHROPIC_API_KEY stays
unset). These tests pin:

- the graph COMPILES via ``build_graph()``;
- the conditional-edge functions (pure) route correctly in isolation;
- the ``update_best`` bookkeeping helper keeps the running max across iterations;
- (hermetic) a fully-mocked end-to-end reaches ``emit`` on a pass path and loops
  at least once on a fail-then-pass path.
"""
import pytest

from config.settings import MAX_COMPILE_RETRIES, MAX_ITERATIONS
from src.pipeline import graph as graph_mod


# --- build_graph: compiles ----------------------------------------------------


def test_build_graph_compiles():
    """build_graph() returns a compiled graph object with an invoke method."""
    compiled = graph_mod.build_graph()
    assert compiled is not None
    assert hasattr(compiled, "invoke")


# --- route_after_identity -----------------------------------------------------


def test_route_after_identity_clean_goes_to_compile():
    state = {"identity_violations": []}
    assert graph_mod.route_after_identity(state) == "compile_node"


def test_route_after_identity_no_key_goes_to_compile():
    """Absent key means no violations recorded -> proceed to compile."""
    assert graph_mod.route_after_identity({}) == "compile_node"


def test_route_after_identity_violations_go_to_writer():
    state = {"identity_violations": ["role[0].company altered"]}
    assert graph_mod.route_after_identity(state) == "writer"


# --- route_after_compile ------------------------------------------------------


def test_route_after_compile_ok_goes_to_recruiter_panel():
    state = {"compile_ok": True, "compile_retries": 0}
    assert graph_mod.route_after_compile(state) == "recruiter_panel"


def test_route_after_compile_fail_with_retries_left_goes_to_writer():
    state = {"compile_ok": False, "compile_retries": 1}
    assert graph_mod.route_after_compile(state) == "writer"


def test_route_after_compile_fail_retries_exhausted_goes_to_emit():
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES}
    assert graph_mod.route_after_compile(state) == "emit"


def test_route_after_compile_fail_retries_over_cap_goes_to_emit():
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES + 1}
    assert graph_mod.route_after_compile(state) == "emit"


# --- route_after_aggregator ---------------------------------------------------


def test_route_after_aggregator_passed_goes_to_emit():
    state = {"passed": True, "iteration": 1}
    assert graph_mod.route_after_aggregator(state) == "emit"


def test_route_after_aggregator_fail_under_cap_goes_to_writer():
    state = {"passed": False, "iteration": 1}
    assert graph_mod.route_after_aggregator(state) == "writer"


def test_route_after_aggregator_fail_just_below_cap_goes_to_writer():
    state = {"passed": False, "iteration": MAX_ITERATIONS - 1}
    assert graph_mod.route_after_aggregator(state) == "writer"


def test_route_after_aggregator_fail_at_cap_goes_to_emit():
    state = {"passed": False, "iteration": MAX_ITERATIONS}
    assert graph_mod.route_after_aggregator(state) == "emit"


def test_route_after_aggregator_fail_over_cap_goes_to_emit():
    state = {"passed": False, "iteration": MAX_ITERATIONS + 1}
    assert graph_mod.route_after_aggregator(state) == "emit"


# --- update_best bookkeeping (pure) -------------------------------------------


def test_update_best_first_iteration_sets_best():
    state = {"aggregate_score": 70.0, "latex_rendered": "DRAFT-A"}
    out = graph_mod.update_best(state)
    assert out["best_score"] == 70.0
    assert out["best_latex"] == "DRAFT-A"


def test_update_best_keeps_higher_of_two():
    state = {
        "aggregate_score": 65.0,
        "latex_rendered": "DRAFT-B",
        "best_score": 80.0,
        "best_latex": "DRAFT-A",
    }
    out = graph_mod.update_best(state)
    # Lower current score must NOT displace the recorded best.
    assert out["best_score"] == 80.0
    assert out["best_latex"] == "DRAFT-A"


def test_update_best_replaces_when_current_is_higher():
    state = {
        "aggregate_score": 91.0,
        "latex_rendered": "DRAFT-C",
        "best_score": 80.0,
        "best_latex": "DRAFT-A",
    }
    out = graph_mod.update_best(state)
    assert out["best_score"] == 91.0
    assert out["best_latex"] == "DRAFT-C"


def test_update_best_max_across_three_iterations():
    """Running the helper iteratively keeps the max, not the last."""
    s1 = graph_mod.update_best({"aggregate_score": 50.0, "latex_rendered": "L1"})
    s2 = graph_mod.update_best(
        {"aggregate_score": 87.0, "latex_rendered": "L2", **s1}
    )
    s3 = graph_mod.update_best(
        {"aggregate_score": 61.0, "latex_rendered": "L3", **s2}
    )
    assert s3["best_score"] == 87.0
    assert s3["best_latex"] == "L2"


def test_update_best_does_not_mutate_input():
    state = {"aggregate_score": 70.0, "latex_rendered": "L", "best_score": 60.0}
    snapshot = dict(state)
    graph_mod.update_best(state)
    assert state == snapshot


# --- hermetic end-to-end (all nodes mocked) -----------------------------------


def _install_fake_nodes(monkeypatch, *, aggregator_behaviour):
    """Monkeypatch every graph node to a canned, key-free return.

    ``aggregator_behaviour`` is a callable(state) -> dict controlling pass/fail
    so a test can force a pass path or a fail-then-pass path.
    """
    monkeypatch.setattr(
        graph_mod, "parse_resume", lambda s: {"resume_struct": "RS", "identity_ledger": "LEDGER"}
    )
    monkeypatch.setattr(graph_mod, "analyze_jd", lambda s: {"jd_vector": "JD"})
    monkeypatch.setattr(
        graph_mod, "gap_analysis", lambda s: {"gap_targets": []}
    )
    monkeypatch.setattr(
        graph_mod, "write_resume", lambda s: {"writer_output": "WO"}
    )
    # render + identity + compile wrappers replaced with clean/success stubs.
    monkeypatch.setattr(
        graph_mod, "render_node", lambda s: {"latex_rendered": "LATEX"}
    )
    monkeypatch.setattr(
        graph_mod,
        "identity_check_node",
        lambda s: {"identity_violations": []},
    )
    monkeypatch.setattr(
        graph_mod,
        "compile_node",
        lambda s: {"compile_ok": True, "compile_errors": "", "pdf_path": "/tmp/x.pdf", "compile_retries": 0},
    )
    monkeypatch.setattr(
        graph_mod,
        "recruiter_panel",
        lambda s: {"panel_scores": []},
    )
    monkeypatch.setattr(graph_mod, "aggregator", aggregator_behaviour)
    # emit is terminal — make it a no-op that records it ran.
    monkeypatch.setattr(
        graph_mod, "emit_node", lambda s: {"emitted": True}
    )


def test_end_to_end_pass_path_reaches_emit(monkeypatch):
    def agg_pass(state):
        return {"passed": True, "aggregate_score": 95.0, "panel_scores": []}

    _install_fake_nodes(monkeypatch, aggregator_behaviour=agg_pass)

    compiled = graph_mod.build_graph()
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0},
        {"recursion_limit": 100},
    )
    assert result.get("emitted") is True
    assert result.get("passed") is True


def test_end_to_end_fail_then_pass_loops_at_least_once(monkeypatch):
    calls = {"n": 0}

    def agg_flip(state):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "passed": False,
                "aggregate_score": 70.0,
                "panel_scores": [],
                "revision_notes": ["1. improve"],
            }
        return {"passed": True, "aggregate_score": 95.0, "panel_scores": []}

    _install_fake_nodes(monkeypatch, aggregator_behaviour=agg_flip)

    compiled = graph_mod.build_graph()
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0},
        {"recursion_limit": 100},
    )
    assert result.get("emitted") is True
    assert calls["n"] >= 2, "aggregator must run at least twice (looped on fail)"
    assert result.get("iteration", 1) >= 2, "iteration counter must have advanced"


def test_end_to_end_compile_fail_exhausts_retries_and_emits(monkeypatch):
    """compile keeps failing -> after MAX_COMPILE_RETRIES the loop hard-emits."""
    def agg_pass(state):  # never reached, but must exist
        return {"passed": True, "aggregate_score": 95.0, "panel_scores": []}

    _install_fake_nodes(monkeypatch, aggregator_behaviour=agg_pass)

    # Override compile to always fail; retries increment inside the node.
    def failing_compile(state):
        retries = state.get("compile_retries", 0) + 1
        return {
            "compile_ok": False,
            "compile_errors": "boom",
            "compile_retries": retries,
        }

    monkeypatch.setattr(graph_mod, "compile_node", failing_compile)

    compiled = graph_mod.build_graph()
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0},
        {"recursion_limit": 100},
    )
    assert result.get("emitted") is True
    # Hard-fail path: never passed, no pdf produced.
    assert result.get("passed") is not True
