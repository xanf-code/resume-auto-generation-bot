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

from config.settings import (
    MAX_COMPILE_RETRIES,
    MAX_IDENTITY_RETRIES,
    MAX_ITERATIONS,
    MAX_LENGTH_RETRIES,
)
from src.pipeline import graph as graph_mod
from src.pipeline.schemas import (
    JDVector,
    PanelScore,
    ResumeRole,
    ResumeStruct,
    RoleBullets,
    SkillWeight,
    WriterOutput,
)


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


# --- route_after_bullet_check -------------------------------------------------


def test_route_after_bullet_check_clean_goes_to_render():
    """No length violations → proceed to render_node."""
    state = {"length_violations": None}
    assert graph_mod.route_after_bullet_check(state) == "render_node"


def test_route_after_bullet_check_empty_list_goes_to_render():
    """Empty violations list (no violations) → proceed to render_node."""
    state = {"length_violations": []}
    assert graph_mod.route_after_bullet_check(state) == "render_node"


def test_route_after_bullet_check_violations_go_to_writer():
    """Length violations present → route back to writer."""
    state = {"length_violations": ["Role 0 bullet 0: 142 chars (SHORT by 16)"]}
    assert graph_mod.route_after_bullet_check(state) == "writer"


def test_route_after_bullet_check_multiple_violations_go_to_writer():
    """Multiple length violations → route back to writer."""
    state = {
        "length_violations": [
            "Role 0 bullet 0: 142 chars (SHORT by 16)",
            "Role 1 bullet 1: 195 chars (LONG by 15)",
        ]
    }
    assert graph_mod.route_after_bullet_check(state) == "writer"


def test_route_after_bullet_check_retries_within_budget_go_to_writer():
    """Violations with retries still under budget → writer (keep fixing)."""
    state = {
        "length_violations": ["Role 0 bullet 0: 180 chars"],
        "length_retries": MAX_LENGTH_RETRIES - 1,
    }
    assert graph_mod.route_after_bullet_check(state) == "writer"


def test_route_after_bullet_check_at_budget_still_retries():
    """length_retries == MAX still allows one more writer bounce (<= boundary)."""
    state = {
        "length_violations": ["Role 0 bullet 0: 180 chars"],
        "length_retries": MAX_LENGTH_RETRIES,
    }
    assert graph_mod.route_after_bullet_check(state) == "writer"


def test_route_after_bullet_check_budget_exhausted_ships_best_effort():
    """Violations but budget exhausted → render_node (option A: ship, never loop)."""
    state = {
        "length_violations": ["Role 0 bullet 0: 180 chars"],
        "length_retries": MAX_LENGTH_RETRIES + 1,
    }
    assert graph_mod.route_after_bullet_check(state) == "render_node"


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


# --- compile_node: page-overflow message (Step 5) ----------------------------


def test_compile_node_single_page_passes(monkeypatch):
    """1-page compile → compile_ok=True, pdf_path surfaced, retries reset."""
    monkeypatch.setattr(graph_mod, "compile_tex", lambda latex: (True, "/tmp/x.pdf", []))
    monkeypatch.setattr(graph_mod, "count_pdf_pages", lambda p: 1)

    result = graph_mod.compile_node({"latex_rendered": "LATEX", "compile_retries": 0})

    assert result["compile_ok"] is True
    assert result["pdf_path"] == "/tmp/x.pdf"
    assert result["compile_retries"] == 0


def test_compile_node_page_overflow_bounces_with_count_remedy(monkeypatch):
    """2-page compile bounces to writer with the count-based remedy.

    Bullets are locked to 195-210 and cannot be shortened below 195, so the
    overflow remedy must target bullet COUNT, not bullet length — and must not
    reference a summary (there is none anymore).
    """
    monkeypatch.setattr(graph_mod, "compile_tex", lambda latex: (True, "/tmp/x.pdf", []))
    monkeypatch.setattr(graph_mod, "count_pdf_pages", lambda p: 2)

    result = graph_mod.compile_node({"latex_rendered": "LATEX", "compile_retries": 1})

    assert result["compile_ok"] is False
    msg = result["compile_errors"]
    # No summary concept remains.
    assert "summary" not in msg.lower()
    # The remedy is count-based and cites the 195-210 band.
    assert "COUNT" in msg
    assert "195-210" in msg
    # Retry counter advanced; no pdf surfaced for an overflowing draft.
    assert result["compile_retries"] == 2
    assert result["pdf_path"] == ""


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
    # Validator stub: no length violations (clean bullets).
    monkeypatch.setattr(
        graph_mod, "check_bullet_lengths", lambda s: {"length_violations": None}
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


# --- length gate fires through the COMPILED graph -----------------------------
#
# The prior bug: `length_violations` was never declared on PipelineState, so
# LangGraph silently dropped check_bullet_lengths' update and the gate was a
# no-op. The router unit tests missed it (they hand-build the state key) and the
# hermetic e2e stubbed the node out. These tests run the REAL check_bullet_lengths
# node inside the compiled graph so the channel plumbing is actually exercised.


def _bullets(n: int) -> WriterOutput:
    """A one-role WriterOutput whose single bullet is exactly ``n`` chars."""
    return WriterOutput(roles=[RoleBullets(index=0, bullets=["x" * n])], skills=["s"])


def _install_fake_nodes_keep_length_gate(monkeypatch, *, writer_behaviour):
    """Like _install_fake_nodes but leaves the REAL check_bullet_lengths wired."""
    monkeypatch.setattr(
        graph_mod, "parse_resume", lambda s: {"resume_struct": "RS", "identity_ledger": "LEDGER"}
    )
    monkeypatch.setattr(graph_mod, "analyze_jd", lambda s: {"jd_vector": "JD"})
    monkeypatch.setattr(graph_mod, "gap_analysis", lambda s: {"gap_targets": []})
    monkeypatch.setattr(graph_mod, "write_resume", writer_behaviour)
    # check_bullet_lengths is intentionally NOT stubbed — it is the unit under test.
    monkeypatch.setattr(graph_mod, "render_node", lambda s: {"latex_rendered": "LATEX"})
    monkeypatch.setattr(
        graph_mod, "identity_check_node", lambda s: {"identity_violations": []}
    )
    monkeypatch.setattr(
        graph_mod,
        "compile_node",
        lambda s: {"compile_ok": True, "compile_errors": "", "pdf_path": "/tmp/x.pdf", "compile_retries": 0},
    )
    monkeypatch.setattr(graph_mod, "recruiter_panel", lambda s: {"panel_scores": []})
    monkeypatch.setattr(
        graph_mod, "aggregator",
        lambda s: {"passed": True, "aggregate_score": 95.0, "panel_scores": []},
    )
    monkeypatch.setattr(graph_mod, "emit_node", lambda s: {"emitted": True})


def test_length_gate_loops_back_then_proceeds(monkeypatch):
    """Underbuilt first draft loops back to writer; a fixed draft then renders.

    This FAILS if length_violations is not a live state channel (the old bug):
    the gate would render the first underbuilt draft and the writer would run
    exactly once.
    """
    calls = {"writer": 0}

    def writer_behaviour(state):
        calls["writer"] += 1
        # First draft is underbuilt (100 < 195); the retry lands in-band (200).
        return {"writer_output": _bullets(100 if calls["writer"] == 1 else 200)}

    _install_fake_nodes_keep_length_gate(monkeypatch, writer_behaviour=writer_behaviour)

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "length_retries": 0},
        {"recursion_limit": 100},
    )

    assert result.get("emitted") is True
    assert calls["writer"] >= 2, (
        "length gate must route the underbuilt draft back to the writer — "
        "if this is 1, length_violations is being dropped again"
    )


def test_length_gate_exhausts_budget_and_still_emits(monkeypatch):
    """Writer that NEVER converges: the loop is bounded and ships best-effort (option A)."""
    calls = {"writer": 0}

    def writer_behaviour(state):
        calls["writer"] += 1
        return {"writer_output": _bullets(100)}  # always underbuilt

    _install_fake_nodes_keep_length_gate(monkeypatch, writer_behaviour=writer_behaviour)

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "length_retries": 0},
        {"recursion_limit": 100},
    )

    # Never crashes on recursion — it ships the best-effort draft.
    assert result.get("emitted") is True
    # Bounded: initial draft + exactly MAX_LENGTH_RETRIES retry bounces.
    assert calls["writer"] == MAX_LENGTH_RETRIES + 1


def test_length_gate_clean_first_draft_does_not_loop(monkeypatch):
    """An in-band first draft renders immediately — writer runs once."""
    calls = {"writer": 0}

    def writer_behaviour(state):
        calls["writer"] += 1
        return {"writer_output": _bullets(200)}  # in-band

    _install_fake_nodes_keep_length_gate(monkeypatch, writer_behaviour=writer_behaviour)

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0, "length_retries": 0},
        {"recursion_limit": 100},
    )

    assert result.get("emitted") is True
    assert calls["writer"] == 1


# --- bookkeep resets the per-iteration length budget --------------------------


def test_bookkeep_resets_length_counters_on_loop():
    """A fail-and-loop bookkeep pass clears length_retries + length_violations."""
    state = {
        "passed": False,
        "iteration": 1,
        "aggregate_score": 60.0,
        "latex_rendered": "L",
        "length_retries": 3,
        "length_violations": ["stale"],
    }
    out = graph_mod.bookkeep_node(state)

    assert out["iteration"] == 2
    assert out["length_retries"] == 0
    assert out["length_violations"] is None


# --- recruiter-panel exact-match cache survives compiled-graph channels -------
#
# Same bug class as the length_violations history above: if panel_cache_latex /
# panel_cache_scores were not declared on PipelineState, LangGraph would drop
# them between node hops and the panel would re-run every iteration even when
# the rendered draft is identical. This test runs the REAL recruiter_panel node
# (only its underlying LLM call, score_one, is mocked) through two iterations
# with byte-identical latex_rendered, and pins that the persona calls fire once.


def test_panel_cache_persists_through_compiled_graph_channels(monkeypatch):
    """Regression guard: an unchanged draft across iterations must NOT
    re-trigger the 4-persona panel — the cache must survive real channel
    plumbing, not just an in-memory dict passed directly to the function."""
    from src.agents import recruiters as recruiters_mod

    call_count = {"n": 0}

    async def fake_score_one(persona_name, system, user):
        call_count["n"] += 1
        return PanelScore(
            persona=persona_name, keyword_match=80, impact_quality=80,
            coherence=80, plausibility=80, formatting=80, notes="ok",
        )

    monkeypatch.setattr(recruiters_mod, "score_one", fake_score_one)

    # recruiter_panel is real here, so its inputs must be real schema
    # instances (it calls .model_dump_json() on both).
    resume_struct = ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp", title="Engineer", start="2020", end="Present",
                source_evidence=["Built things."],
            ),
        ],
        education=["BS Computer Science"],
        skills=["Python"],
    )
    jd_vector = JDVector(
        weighted_skills=[SkillWeight(name="Python", weight=0.9)],
        ats_keywords=["Python"],
        seniority="mid",
        must_mirror=["Python"],
    )

    monkeypatch.setattr(
        graph_mod, "parse_resume",
        lambda s: {"resume_struct": resume_struct, "identity_ledger": "LEDGER"},
    )
    monkeypatch.setattr(graph_mod, "analyze_jd", lambda s: {"jd_vector": jd_vector})
    monkeypatch.setattr(graph_mod, "gap_analysis", lambda s: {"gap_targets": []})
    monkeypatch.setattr(graph_mod, "write_resume", lambda s: {"writer_output": "WO"})
    monkeypatch.setattr(graph_mod, "check_bullet_lengths", lambda s: {"length_violations": None})
    # render_node ALWAYS emits the identical draft — the exact case the cache targets.
    monkeypatch.setattr(graph_mod, "render_node", lambda s: {"latex_rendered": "SAME LATEX EVERY TIME"})
    monkeypatch.setattr(graph_mod, "identity_check_node", lambda s: {"identity_violations": []})
    monkeypatch.setattr(
        graph_mod, "compile_node",
        lambda s: {"compile_ok": True, "compile_errors": "", "pdf_path": "/tmp/x.pdf", "compile_retries": 0},
    )
    # recruiter_panel is intentionally left REAL — it is the unit under test.

    agg_calls = {"n": 0}

    def agg_flip(state):
        agg_calls["n"] += 1
        if agg_calls["n"] == 1:
            return {"passed": False, "aggregate_score": 70.0, "revision_notes": ["1. improve"]}
        return {"passed": True, "aggregate_score": 95.0}

    monkeypatch.setattr(graph_mod, "aggregator", agg_flip)
    monkeypatch.setattr(graph_mod, "emit_node", lambda s: {"emitted": True})

    compiled = graph_mod.build_graph(enable_scoring=False)
    result = compiled.invoke(
        {"resume_tex_raw": "R", "jd_raw": "J", "iteration": 1, "compile_retries": 0},
        {"recursion_limit": 100},
    )

    assert result.get("emitted") is True
    assert agg_calls["n"] >= 2, "aggregator must run at least twice (looped on fail)"
    assert call_count["n"] == 4, (
        "panel_cache_latex/panel_cache_scores must survive LangGraph's channel "
        "plumbing across iterations — if this is 8, the cache state is being "
        "dropped between node hops and the panel re-ran on the second, "
        "identical draft"
    )
