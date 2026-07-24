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

from config.settings import MAX_COMPILE_RETRIES, MAX_IDENTITY_RETRIES, MAX_ITERATIONS
from src.pipeline import graph as graph_mod


# --- build_graph: compiles ----------------------------------------------------


def test_build_graph_compiles():
    """build_graph() returns a compiled graph object with an invoke method."""
    compiled = graph_mod.build_graph(enable_scoring=False)
    assert compiled is not None
    assert hasattr(compiled, "invoke")


def test_build_graph_with_scoring_enabled():
    """build_graph(enable_scoring=True) wires the score_report node."""
    compiled = graph_mod.build_graph(enable_scoring=True)
    assert compiled is not None
    assert hasattr(compiled, "invoke")


def test_end_to_end_with_scoring_enabled(monkeypatch):
    """When enable_scoring=True, score_report_node runs after emit."""
    def agg_pass(state):
        return {"passed": True, "aggregate_score": 95.0, "panel_scores": []}

    _install_fake_nodes(monkeypatch, aggregator_behaviour=agg_pass)

    # Mock score_report_node to track that it ran
    score_report_called = {"called": False}

    def fake_score_report(state):
        score_report_called["called"] = True
        return {"score_report_md": "/tmp/report.md"}

    monkeypatch.setattr(graph_mod, "score_report_node", fake_score_report)

    compiled = graph_mod.build_graph(enable_scoring=True)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "enable_scoring": True},
        {"recursion_limit": 100},
    )

    assert result.get("emitted") is True
    assert score_report_called["called"] is True
    assert result.get("score_report_md") == "/tmp/report.md"


def test_end_to_end_without_scoring_skips_score_report(monkeypatch):
    """When enable_scoring=False (default), score_report_node does NOT run."""
    def agg_pass(state):
        return {"passed": True, "aggregate_score": 95.0, "panel_scores": []}

    _install_fake_nodes(monkeypatch, aggregator_behaviour=agg_pass)

    # Mock score_report_node to track that it should NOT be called
    score_report_called = {"called": False}

    def fake_score_report(state):
        score_report_called["called"] = True
        return {"score_report_md": "/tmp/report.md"}

    monkeypatch.setattr(graph_mod, "score_report_node", fake_score_report)

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "enable_scoring": False},
        {"recursion_limit": 100},
    )

    assert result.get("emitted") is True
    assert score_report_called["called"] is False
    assert "score_report_md" not in result


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


def test_route_after_identity_bounces_within_budget():
    """Violations with retries still under budget → writer, not emit."""
    state = {
        "identity_violations": ["role[0].company altered"],
        "identity_retries": MAX_IDENTITY_RETRIES - 1,
    }
    assert graph_mod.route_after_identity(state) == "writer"


def test_route_after_identity_exhausted_routes_to_emit():
    """Budget exhausted → emit (fail gracefully) instead of looping forever."""
    state = {
        "identity_violations": ["role[0].company altered"],
        "identity_retries": MAX_IDENTITY_RETRIES,
    }
    assert graph_mod.route_after_identity(state) == "emit"


def test_route_after_identity_exhausted_over_cap_routes_to_emit():
    state = {
        "identity_violations": ["x"],
        "identity_retries": MAX_IDENTITY_RETRIES + 2,
    }
    assert graph_mod.route_after_identity(state) == "emit"


def test_identity_check_node_increments_retries(monkeypatch):
    """identity_check_node increments identity_retries when violations are found."""
    monkeypatch.setattr(
        graph_mod, "check_identity",
        lambda latex, ledger: (False, ["role[0].company missing"]),
    )
    state = {
        "latex_rendered": "LATEX",
        "identity_ledger": object(),
        "identity_retries": 2,
    }
    result = graph_mod.identity_check_node(state)
    assert result["identity_retries"] == 3
    assert result["identity_violations"] == ["role[0].company missing"]


def test_identity_check_node_clean_does_not_include_retries(monkeypatch):
    """Clean pass must NOT include identity_retries so the global budget is preserved."""
    monkeypatch.setattr(
        graph_mod, "check_identity",
        lambda latex, ledger: (True, []),
    )
    state = {
        "latex_rendered": "LATEX",
        "identity_ledger": object(),
        "identity_retries": 3,
    }
    result = graph_mod.identity_check_node(state)
    assert "identity_retries" not in result
    assert result["identity_violations"] == []


# --- route_after_compile ------------------------------------------------------


def test_route_after_compile_ok_goes_to_recruiter_panel():
    state = {"compile_ok": True, "compile_retries": 0}
    assert graph_mod.route_after_compile(state) == "recruiter_panel"


def test_route_after_compile_fail_with_retries_left_goes_to_writer():
    state = {"compile_ok": False, "compile_retries": 1}
    assert graph_mod.route_after_compile(state) == "writer"


def test_route_after_compile_fail_retries_exhausted_goes_to_emit():
    # After the Issue 4 fix (<= boundary), compile_retries==MAX_COMPILE_RETRIES
    # still routes to "writer" (one more bounce is allowed at exactly MAX).
    # compile_retries==MAX+1 is the true exhaustion point that routes to emit.
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES + 1}
    assert graph_mod.route_after_compile(state) == "emit"


def test_route_after_compile_fail_retries_over_cap_goes_to_emit():
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES + 2}
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
    state = {"aggregate_score": 70.0, "latex_rendered": "DRAFT-A", "pdf_path": "/tmp/a.pdf"}
    out = graph_mod.update_best(state)
    assert out["best_score"] == 70.0
    assert out["best_latex"] == "DRAFT-A"
    assert out["best_pdf_path"] == "/tmp/a.pdf"


def test_update_best_captures_pdf_path():
    """When a new best score is set, best_pdf_path is captured alongside best_latex."""
    state = {"aggregate_score": 85.0, "latex_rendered": "DRAFT-X", "pdf_path": "/tmp/x.pdf"}
    out = graph_mod.update_best(state)
    assert out["best_pdf_path"] == "/tmp/x.pdf"


def test_update_best_does_not_capture_pdf_path_when_score_not_higher():
    """When score doesn't beat best, old best_pdf_path is preserved, not replaced."""
    state = {
        "aggregate_score": 65.0,
        "latex_rendered": "DRAFT-B",
        "pdf_path": "/tmp/worse.pdf",
        "best_score": 80.0,
        "best_latex": "DRAFT-A",
        "best_pdf_path": "/tmp/best.pdf",
    }
    out = graph_mod.update_best(state)
    assert out["best_pdf_path"] == "/tmp/best.pdf"


def test_update_best_keeps_higher_of_two():
    state = {
        "aggregate_score": 65.0,
        "latex_rendered": "DRAFT-B",
        "best_score": 80.0,
        "best_latex": "DRAFT-A",
        "best_pdf_path": "/tmp/best.pdf",
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

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "enable_scoring": False},
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

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "enable_scoring": False},
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

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "enable_scoring": False},
        {"recursion_limit": 100},
    )
    assert result.get("emitted") is True
    # Hard-fail path: never passed, no pdf produced.
    assert result.get("passed") is not True


# --- Issue 4: compile retry off-by-one (route_after_compile) ------------------


def test_route_after_compile_allows_retry_at_max():
    """compile_ok=False, compile_retries==MAX_COMPILE_RETRIES -> writer (not emit).

    Before the fix: `retries < MAX` evaluated False when retries==MAX, so it
    incorrectly returned 'emit' and consumed only 3 writer retries instead of 4.
    After the fix: `retries <= MAX` lets the Nth writer bounce happen.
    """
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES}
    assert graph_mod.route_after_compile(state) == "writer"


def test_route_after_compile_emits_when_over_max():
    """compile_ok=False, compile_retries==MAX+1 -> emit (budget truly exhausted)."""
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES + 1}
    assert graph_mod.route_after_compile(state) == "emit"


def test_route_after_compile_emits_at_exactly_max_plus_one():
    """Alias for clarity: compile_retries==MAX+1 -> emit."""
    state = {"compile_ok": False, "compile_retries": MAX_COMPILE_RETRIES + 1}
    assert graph_mod.route_after_compile(state) == "emit"


# --- Issue 6: identity_retries reset on clean (identity_check_node) -----------


def test_identity_check_node_clean_preserves_existing_retries(monkeypatch):
    """Clean pass with identity_retries=2 -> returned dict must NOT contain identity_retries.

    LangGraph only updates keys that are present in the returned dict.
    Omitting the key preserves the existing global budget (2 stays 2).
    """
    monkeypatch.setattr(
        graph_mod,
        "check_identity",
        lambda latex, ledger: (True, []),
    )
    state = {
        "latex_rendered": "LATEX",
        "identity_ledger": "LEDGER",
        "identity_retries": 2,
    }
    result = graph_mod.identity_check_node(state)
    assert "identity_retries" not in result, (
        "identity_retries must be absent from the returned dict on a clean pass "
        "so LangGraph does not overwrite the global budget counter"
    )
    assert result["identity_violations"] == []


def test_identity_check_node_clean_preserves_zero_retries(monkeypatch):
    """Clean pass with identity_retries=0 -> returned dict must NOT contain identity_retries."""
    monkeypatch.setattr(
        graph_mod,
        "check_identity",
        lambda latex, ledger: (True, []),
    )
    state = {
        "latex_rendered": "LATEX",
        "identity_ledger": "LEDGER",
        "identity_retries": 0,
    }
    result = graph_mod.identity_check_node(state)
    assert "identity_retries" not in result
    assert result["identity_violations"] == []
