"""LangGraph wiring - the full revision loop as a ``StateGraph``.

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

from src.agents.aggregator import aggregator
from src.agents.gap_analyzer import gap_analysis
from src.agents.jd_analyzer import analyze_jd
from src.agents.parser import parse_resume
from src.agents.project_selector import project_select
from src.agents.recruiters import recruiter_panel
from src.agents.skills import generate_skills
from src.agents.validators import check_bullet_lengths
from src.agents.writer import write_resume
from src.compiler.identity_check import check_identity
from src.compiler.renderer import patch_project_bullets, render
from src.compiler.tectonic import compile_tex, count_pdf_pages
from src.pipeline.emit import emit_node
from src.pipeline.state import PipelineState
from src.pipeline.tuning import get_tuning


# --- compiler node wrappers ---------------------------------------------------


def render_node(state: PipelineState) -> dict:
    """Node: patch the original .tex with the writer's bullets and project section."""
    log.info("render       | patching bullet blocks in original .tex")
    latex = render(state["resume_tex_raw"], state["identity_ledger"], state["writer_output"])
    project_bullets = state.get("project_bullets")
    selected_projects = state.get("selected_projects")
    if project_bullets and selected_projects:
        log.info("render       | patching projects section (%d projects)", len(project_bullets))
        latex = patch_project_bullets(latex, selected_projects, project_bullets)
    log.info("render       | LaTeX ready - %d chars", len(latex))
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
            "identity_chk | VIOLATIONS DETECTED (%d) - identity_retries %d→%d",
            len(violations), current_retries, new_retries,
        )
        for v in violations:
            log.warning("identity_chk |   %s", v)
        return {"identity_violations": list(violations), "identity_retries": new_retries}
    log.info("identity_chk | CLEAN ✓ - all identity fields verified verbatim")
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
                "compile      | PAGE OVERFLOW - %d pages → bouncing to writer", pages
            )
            return {
                "compile_ok": False,
                "compile_errors": (
                    f"PAGE OVERFLOW: the resume compiled to {pages} pages but MUST fit "
                    f"exactly 1 page. Every bullet is locked to the 195-210 char band "
                    f"and CANNOT be shortened below 195 - the lever is bullet COUNT, "
                    f"not bullet length. ACTION: cut the lowest-value bullet(s) from the "
                    f"role(s) carrying the most bullets (fixed budget: 7 total, "
                    f"role 0 = exactly 4, role 1 = exactly 3). Do NOT add new content "
                    f"and do NOT shorten bullets below 195."
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
    log.warning("compile      | FAILED - %d error(s)", len(errors))
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
    best_score = state.get("best_score")

    if current_score is None:
        return {}
    if best_score is None or current_score > best_score:
        return {
            "best_score": current_score,
            "best_latex": state.get("latex_rendered", ""),
            "best_pdf_path": state.get("pdf_path", ""),
        }
    # Not a new best: omit the keys entirely rather than re-stating them.
    # LangGraph only overwrites keys present in the return value (same
    # invariant identity_check_node documents), so returning {} preserves
    # best_* untouched instead of risking a "" clobber via .get(..., "").
    return {}


def bookkeep_node(state: PipelineState) -> dict:
    """Node: update best-scoring draft, then decide the single route.

    Writes an explicit ``route`` field ("emit" | "writer") that
    ``route_after_aggregator`` reads verbatim. This node is the only place
    that decides pass/fail/cap-hit; ``route_after_aggregator`` used to
    re-derive the same decision from ``passed``/``iteration`` independently,
    which relied on the cap-hit branch never incrementing ``iteration``
    while the fail branch does - correct today, but a refactor that moved
    the increment could desync the two silently. Single source of truth
    removes that risk.
    """
    best = update_best(state)
    passed = bool(state.get("passed", False))
    iteration = state.get("iteration", 1)
    agg = state.get("aggregate_score")
    if agg is None:
        log.warning(
            "bookkeep     | aggregate_score missing from state - aggregator likely "
            "failed to produce a score; treating as 0.0 (failing score, loops to writer)"
        )
        agg = 0.0
    best_so_far = best.get("best_score", agg)
    max_iterations = get_tuning(state).max_iterations

    if passed:
        log.info("bookkeep     | PASSED - aggregate=%.2f, emitting", agg)
        return {**best, "cap_hit": False, "route": "emit"}
    if iteration >= max_iterations:
        log.warning(
            "bookkeep     | CAP HIT (iteration=%d/%d) - emitting best=%.2f",
            iteration, max_iterations, best_so_far,
        )
        return {**best, "cap_hit": True, "route": "emit"}
    log.info(
        "bookkeep     | fail - iteration %d→%d, best_score=%.2f → looping to writer",
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
        "route": "writer",
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
    if state.get("identity_retries", 0) <= get_tuning(state).max_identity_retries:
        return "writer"
    log.warning(
        "identity_chk | identity_retries budget exhausted (%d) - routing to emit",
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
    if state.get("length_retries", 0) <= get_tuning(state).max_length_retries:
        return "writer"
    log.warning(
        "check_bullet_lengths | length_retries budget exhausted (%d) - proceeding "
        "to render with best-effort draft",
        state.get("length_retries", 0),
    )
    return "render_node"


def route_after_compile(state: PipelineState) -> str:
    """ok → ``recruiter_panel``; fail & retries left → ``writer``; else ``emit``.

    The compile-retry budget is ``MAX_COMPILE_RETRIES`` PER iteration and lives
    on ``compile_retries`` - independent of the main ``iteration`` counter.

    Budget interaction: a writer bounce from here re-enters at ``writer`` and
    flows back through ``check_bullet_lengths`` and ``identity_check_node``
    before reaching ``compile_node`` again. Those nodes own ``length_retries``
    / ``identity_retries`` and neither is reset by a compile bounce - only
    ``bookkeep_node`` resets all three on a full iteration loop. So a single
    iteration that ping-pongs compile→writer→length→writer→identity→writer
    can burn all three budgets before ``bookkeep_node`` ever runs; the
    effective per-iteration writer-call ceiling is the SUM of the three
    retry budgets, not any single one of them. This is intentional
    (fail-fast), not a bug - noted here so ``max_iterations`` isn't mistaken
    for the only multiplier on LLM spend.
    """
    if state.get("compile_ok"):
        return "recruiter_panel"
    if state.get("compile_retries", 0) <= get_tuning(state).max_compile_retries:
        return "writer"
    return "emit"


def route_after_aggregator(state: PipelineState) -> str:
    """Read the route ``bookkeep_node`` already decided.

    ``bookkeep_node`` is the sole owner of the pass/fail/cap-hit decision; this
    function just forwards its ``route`` field rather than re-deriving the
    same branch from ``passed``/``iteration`` (see Gap 6 in bookkeep_node's
    docstring). Defaults to ``"emit"`` if ``route`` is ever absent, so a
    missing field fails safe instead of looping forever.
    """
    return state.get("route", "emit")


# --- graph assembly -----------------------------------------------------------


def build_graph(enable_scoring: bool = False):
    """Build and compile the pipeline ``StateGraph``.

    Args:
        enable_scoring: Accepted for API compatibility. Persona panel scoring
            (``score_report.json``) always runs via recruiter_panel → emit.
            The post-emit ``resume_scorer`` markdown report is never wired.

    Returns a compiled graph exposing ``.invoke(state, config)``. Node function
    references are looked up on this module at wire-time so tests can monkeypatch
    them for hermetic end-to-end runs.
    """
    # enable_scoring kept for API/CLI compatibility; topology ignores it.
    _ = enable_scoring
    builder = StateGraph(PipelineState)

    # Nodes are registered via module-level lookups so monkeypatching the
    # module attribute (e.g. graph.compile_node) is honoured at build time.
    builder.add_node("parse_resume", parse_resume)
    builder.add_node("analyze_jd", analyze_jd)
    builder.add_node("gap_analysis", gap_analysis)
    builder.add_node("generate_skills", generate_skills)
    builder.add_node("project_select", project_select)
    builder.add_node("writer", write_resume)
    builder.add_node("check_bullet_lengths", check_bullet_lengths)
    builder.add_node("render_node", render_node)
    builder.add_node("identity_check_node", identity_check_node)
    builder.add_node("compile_node", compile_node)
    builder.add_node("recruiter_panel", recruiter_panel)
    builder.add_node("aggregator", aggregator)
    builder.add_node("bookkeep", bookkeep_node)
    builder.add_node("emit", emit_node)

    # Linear extraction spine - generate_skills and project_select fire once each
    # before the writer loop. Back-edges all re-enter at writer, skipping both.
    builder.add_edge(START, "parse_resume")
    builder.add_edge("parse_resume", "analyze_jd")
    builder.add_edge("analyze_jd", "gap_analysis")
    builder.add_edge("gap_analysis", "generate_skills")
    builder.add_edge("generate_skills", "project_select")
    builder.add_edge("project_select", "writer")

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

    # Persona scores land in score_report.json via emit. Do not wire
    # score_report_node / resume_scorer - that path is intentionally unused.
    builder.add_edge("emit", END)

    return builder.compile()
