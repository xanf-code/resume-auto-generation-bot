"""LangGraph wiring — the full revision loop as a ``StateGraph``.

Topology::

    parse_resume → analyze_jd → gap_analysis → generate_skills → writer → check_bullet_lengths
                                                                     ▲          │    │
                                                                     │          │ (clean)
                                                                     │          │    │
                                             (length violation) ─────┘     render_node
                                                                                 │
                                                                         identity_check_node
                                                                                 │
                                          (identity violation) ──────────┐   (clean)
                                                                         │       │
                                               writer ◀── (compile fail, │   compile_node
                                                revision  ≤ retries) ◀──┤       │
                                                bounce)                  │ ┌─────┴── (ok)
                                                                         │ │
                                            (retries exhausted) ─────────┤ recruiter_panel
                                                                         │     │
                                                                      emit   aggregator
                                                                         ▲     │
                                             (pass / cap hit) ───────────┴── bookkeep
                                                                               │
                                             (fail & iter < MAX) ──▶ writer

``generate_skills`` fires exactly once: the graph's back-edges all re-enter at
``writer``, never before it, so skill_dump is invariant across revisions.

The four conditional-edge functions are pure and independently unit-tested.
Node wrappers around the plain compiler functions (``render``, ``check_identity``,
``compile_tex``) adapt them to the state-in/state-out node contract.
"""
import logging

from langgraph.graph import END, START, StateGraph

log = logging.getLogger(__name__)

from config.settings import (
    MAX_COMPILE_RETRIES,
    MAX_IDENTITY_RETRIES,
    MAX_ITERATIONS,
    MAX_LENGTH_RETRIES,
)
from src.agents.aggregator import aggregator
from src.agents.gap_analyzer import gap_analysis
from src.agents.jd_analyzer import analyze_jd
from src.agents.parser import parse_resume
from src.agents.recruiters import recruiter_panel
from src.agents.skills import generate_skills
from src.agents.validators import check_bullet_lengths
from src.agents.writer import write_resume
from src.compiler.identity_check import check_identity
from src.compiler.renderer import render
from src.compiler.tectonic import compile_tex, count_pdf_pages
from src.pipeline.emit import emit_node
from src.pipeline.score_report import score_report_node
from src.pipeline.state import PipelineState


# --- compiler node wrappers ---------------------------------------------------


def render_node(state: PipelineState) -> dict:
    """Node: patch the original .tex with the writer's bullets."""
    log.info("render       | patching bullet blocks in original .tex")
    latex = render(state["resume_tex_raw"], state["identity_ledger"], state["writer_output"])
    log.info("render       | LaTeX ready — %d chars", len(latex))
    return {"latex_rendered": latex}


def identity_check_node(state: PipelineState) -> dict:
    """Node: mechanical identity tripwire over the rendered LaTeX."""
    log.info("identity_chk | diffing rendered LaTeX against ledger…")
    _ok, violations = check_identity(
        state["latex_rendered"], state["identity_ledger"]
    )
    current_retries = state.get("identity_retries", 0)
    if violations:
        new_retries = current_retries + 1
        log.warning(
            "identity_chk | VIOLATIONS DETECTED (%d) — identity_retries %d→%d",
            len(violations), current_retries, new_retries,
        )
        for v in violations:
            log.warning("identity_chk |   %s", v)
        return {"identity_violations": list(violations), "identity_retries": new_retries}
    log.info("identity_chk | CLEAN ✓ — all identity fields verified verbatim")
    # Do NOT include identity_retries in the returned dict on a clean pass.
    # LangGraph only overwrites keys present in the return value; omitting the
    # key preserves the global budget counter across iterations (Issue 6 fix).
    return {"identity_violations": []}


def compile_node(state: PipelineState) -> dict:
    """Node: compile the rendered LaTeX to PDF, then enforce the 1-page hard cap."""
    retries = state.get("compile_retries", 0)
    log.info("compile      | running tectonic (compile_retries=%d)…", retries)
    ok, pdf_path, errors = compile_tex(state["latex_rendered"])
    if ok:
        pages = count_pdf_pages(pdf_path)
        if pages > 1:
            log.warning(
                "compile      | PAGE OVERFLOW — %d pages → bouncing to writer", pages
            )
            return {
                "compile_ok": False,
                "compile_errors": (
                    f"PAGE OVERFLOW: the resume compiled to {pages} pages but MUST fit "
                    f"exactly 1 page. Every bullet is locked to the 195-210 char band "
                    f"and CANNOT be shortened below 195 — the lever is bullet COUNT, "
                    f"not bullet length. ACTION: cut the lowest-value bullet(s) from the "
                    f"role(s) carrying the most bullets (stay within the 8-total / "
                    f"5-per-role caps). Do NOT add new content and do NOT shorten bullets "
                    f"below 195."
                ),
                "pdf_path": "",
                "compile_retries": retries + 1,
            }
        log.info("compile      | OK ✓ → %s  (pages=%d)", pdf_path, pages)
        return {
            "compile_ok": True,
            "compile_errors": "",
            "pdf_path": pdf_path or "",
            "compile_retries": 0,
        }
    log.warning("compile      | FAILED — %d error(s)", len(errors))
    for e in errors:
        log.warning("compile      |   %s", e)
    return {
        "compile_ok": False,
        "compile_errors": "\n".join(errors),
        "pdf_path": "",
        "compile_retries": retries + 1,
    }


# --- bookkeeping --------------------------------------------------------------


def update_best(state: PipelineState) -> dict:
    """Pure helper: keep the running max of (score, latex, pdf).

    Returns a NEW dict with ``best_score`` / ``best_latex`` / ``best_pdf_path``
    reflecting the highest score seen so far. Skills are invariant across
    iterations (produced once by ``generate_skills``) so there is nothing to
    snapshot here. Never mutates ``state``.
    """
    current_score = state.get("aggregate_score")
    current_latex = state.get("latex_rendered", "")
    current_pdf = state.get("pdf_path", "")
    best_score = state.get("best_score")

    if current_score is None:
        return {}
    if best_score is None or current_score > best_score:
        return {
            "best_score": current_score,
            "best_latex": current_latex,
            "best_pdf_path": current_pdf,
        }
    return {
        "best_score": best_score,
        "best_latex": state.get("best_latex", ""),
        "best_pdf_path": state.get("best_pdf_path", ""),
    }


def bookkeep_node(state: PipelineState) -> dict:
    """Node: update best-scoring draft, then route on pass/fail/cap."""
    best = update_best(state)
    passed = bool(state.get("passed", False))
    iteration = state.get("iteration", 1)
    agg = state.get("aggregate_score", 0.0)
    best_so_far = best.get("best_score", agg)

    if passed:
        log.info("bookkeep     | PASSED — aggregate=%.2f, emitting", agg)
        return {**best, "cap_hit": False}
    if iteration >= MAX_ITERATIONS:
        log.warning(
            "bookkeep     | CAP HIT (iteration=%d/%d) — emitting best=%.2f",
            iteration, MAX_ITERATIONS, best_so_far,
        )
        return {**best, "cap_hit": True}
    log.info(
        "bookkeep     | fail — iteration %d→%d, best_score=%.2f → looping to writer",
        iteration, iteration + 1, best_so_far,
    )
    # Reset per-iteration counters so the next revision gets fresh budgets and
    # never inherits a stale length_violations list from the prior iteration.
    return {
        **best,
        "iteration": iteration + 1,
        "compile_retries": 0,
        "length_retries": 0,
        "length_violations": None,
    }


# --- conditional-edge functions (pure, independently tested) ------------------


def route_after_identity(state: PipelineState) -> str:
    """Route based on violations and retry budget.

    - No violations → ``compile_node``
    - Violations AND budget remains → ``writer`` (violations injected into prompt)
    - Violations AND budget exhausted → ``emit`` (fail gracefully with best draft)
    """
    if not state.get("identity_violations"):
        return "compile_node"
    if state.get("identity_retries", 0) < MAX_IDENTITY_RETRIES:
        return "writer"
    log.warning(
        "identity_chk | identity_retries budget exhausted (%d) — routing to emit",
        state.get("identity_retries", 0),
    )
    return "emit"


def route_after_bullet_check(state: PipelineState) -> str:
    """Route based on bullet length violations and the retry budget.

    - No violations → ``render_node`` (proceed to render)
    - Violations AND budget remains → ``writer`` (fix length violations)
    - Violations AND budget exhausted → ``render_node`` (ship best-effort draft)

    Length is a cosmetic gate, not an integrity gate: if the writer cannot
    converge to the band after ``MAX_LENGTH_RETRIES`` tries, the pipeline
    proceeds with the last draft rather than looping forever (option A).
    """
    if not state.get("length_violations"):
        return "render_node"
    if state.get("length_retries", 0) <= MAX_LENGTH_RETRIES:
        return "writer"
    log.warning(
        "check_bullet_lengths | length_retries budget exhausted (%d) — proceeding "
        "to render with best-effort draft",
        state.get("length_retries", 0),
    )
    return "render_node"


def route_after_compile(state: PipelineState) -> str:
    """ok → ``recruiter_panel``; fail & retries left → ``writer``; else ``emit``.

    The compile-retry budget is ``MAX_COMPILE_RETRIES`` PER iteration and lives
    on ``compile_retries`` — independent of the main ``iteration`` counter.
    """
    if state.get("compile_ok"):
        return "recruiter_panel"
    if state.get("compile_retries", 0) <= MAX_COMPILE_RETRIES:
        return "writer"
    return "emit"


def route_after_aggregator(state: PipelineState) -> str:
    """passed → ``emit``; else iter < MAX → ``writer``; else ``emit`` (cap)."""
    if state.get("passed"):
        return "emit"
    if state.get("iteration", 1) < MAX_ITERATIONS:
        return "writer"
    return "emit"


# --- graph assembly -----------------------------------------------------------


def build_graph(enable_scoring: bool = False):
    """Build and compile the pipeline ``StateGraph``.

    Args:
        enable_scoring: If True, wire the score_report node after emit

    Returns a compiled graph exposing ``.invoke(state, config)``. Node function
    references are looked up on this module at wire-time so tests can monkeypatch
    them for hermetic end-to-end runs.
    """
    builder = StateGraph(PipelineState)

    # Nodes are registered via module-level lookups so monkeypatching the
    # module attribute (e.g. graph.compile_node) is honoured at build time.
    builder.add_node("parse_resume", parse_resume)
    builder.add_node("analyze_jd", analyze_jd)
    builder.add_node("gap_analysis", gap_analysis)
    builder.add_node("generate_skills", generate_skills)
    builder.add_node("writer", write_resume)
    builder.add_node("check_bullet_lengths", check_bullet_lengths)
    builder.add_node("render_node", render_node)
    builder.add_node("identity_check_node", identity_check_node)
    builder.add_node("compile_node", compile_node)
    builder.add_node("recruiter_panel", recruiter_panel)
    builder.add_node("aggregator", aggregator)
    builder.add_node("bookkeep", bookkeep_node)
    builder.add_node("emit", emit_node)

    # Linear extraction spine — generate_skills fires once before the writer loop.
    builder.add_edge(START, "parse_resume")
    builder.add_edge("parse_resume", "analyze_jd")
    builder.add_edge("analyze_jd", "gap_analysis")
    builder.add_edge("gap_analysis", "generate_skills")
    builder.add_edge("generate_skills", "writer")

    # Writer → bullet length check → render → identity check.
    # Length violations route back to writer; clean bullets proceed to render.
    builder.add_edge("writer", "check_bullet_lengths")
    builder.add_conditional_edges(
        "check_bullet_lengths",
        route_after_bullet_check,
        {"writer": "writer", "render_node": "render_node"},
    )
    builder.add_edge("render_node", "identity_check_node")

    # identity: violations (within budget) → writer; exhausted → emit; clean → compile.
    builder.add_conditional_edges(
        "identity_check_node",
        route_after_identity,
        {"writer": "writer", "compile_node": "compile_node", "emit": "emit"},
    )

    # compile: ok → panel; fail (retries left) → writer; exhausted → emit.
    builder.add_conditional_edges(
        "compile_node",
        route_after_compile,
        {"recruiter_panel": "recruiter_panel", "writer": "writer", "emit": "emit"},
    )

    # panel → aggregator → bookkeep.
    builder.add_edge("recruiter_panel", "aggregator")
    builder.add_edge("aggregator", "bookkeep")

    # bookkeep: pass/cap → emit; fail & under cap → writer.
    builder.add_conditional_edges(
        "bookkeep",
        route_after_aggregator,
        {"emit": "emit", "writer": "writer"},
    )

    # Conditionally wire score_report node if scoring is enabled
    if enable_scoring:
        builder.add_node("score_report", score_report_node)
        builder.add_edge("emit", "score_report")
        builder.add_edge("score_report", END)
    else:
        # emit goes directly to END when scoring is disabled
        builder.add_edge("emit", END)

    return builder.compile()
