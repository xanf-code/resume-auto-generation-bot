"""LangGraph wiring — the full revision loop as a ``StateGraph``.

Topology::

    parse_resume → analyze_jd → gap_analysis → writer → render_node
                     ▲                                      │
                     │                              identity_check_node
                     │                                      │
     (identity violation) ──────────────────────────┐  (clean)
                     │                               │      │
                     └── writer ◀── (compile fail,   │  compile_node
                          revision  ≤ retries)  ◀────┤      │
                          bounce)                    │  ┌───┴── (ok)
                                                     │  │
                       (retries exhausted) ──────────┴──┤   recruiter_panel
                                                        │      │
                                                     emit    aggregator
                                                        ▲      │
                                    (pass / cap hit) ───┴── bookkeep
                                                               │
                                    (fail & iter < MAX) ──▶ writer

The three conditional-edge functions are pure and independently unit-tested.
Node wrappers around the plain compiler functions (``render``, ``check_identity``,
``compile_tex``) adapt them to the state-in/state-out node contract.
"""
from langgraph.graph import END, START, StateGraph

from config.settings import MAX_COMPILE_RETRIES, MAX_ITERATIONS
from src.agents.aggregator import aggregator
from src.agents.gap_analyzer import gap_analysis
from src.agents.jd_analyzer import analyze_jd
from src.agents.parser import parse_resume
from src.agents.recruiters import recruiter_panel
from src.agents.writer import write_resume
from src.compiler.identity_check import check_identity
from src.compiler.renderer import render
from src.compiler.tectonic import compile_tex
from src.pipeline.emit import emit_node
from src.pipeline.state import PipelineState


# --- compiler node wrappers ---------------------------------------------------


def render_node(state: PipelineState) -> dict:
    """Node: render the locked ledger + writer output into LaTeX."""
    latex = render(state["identity_ledger"], state["writer_output"])
    return {"latex_rendered": latex}


def identity_check_node(state: PipelineState) -> dict:
    """Node: mechanical identity tripwire over the rendered LaTeX.

    Records ``identity_violations`` (empty when clean). A non-empty list routes
    back to the writer via ``route_after_identity``.
    """
    _ok, violations = check_identity(
        state["latex_rendered"], state["identity_ledger"]
    )
    return {"identity_violations": list(violations)}


def compile_node(state: PipelineState) -> dict:
    """Node: compile the rendered LaTeX to PDF.

    On failure, increments the per-iteration ``compile_retries`` counter (kept
    separate from the main ``iteration`` counter so a compile bounce never
    consumes a revision iteration). On success, resets it to 0.
    """
    ok, pdf_path, errors = compile_tex(state["latex_rendered"])
    if ok:
        return {
            "compile_ok": True,
            "compile_errors": "",
            "pdf_path": pdf_path or "",
            "compile_retries": 0,
        }
    return {
        "compile_ok": False,
        "compile_errors": "\n".join(errors),
        "pdf_path": "",
        "compile_retries": state.get("compile_retries", 0) + 1,
    }


# --- bookkeeping --------------------------------------------------------------


def update_best(state: PipelineState) -> dict:
    """Pure helper: keep the running max of (aggregate_score, latex_rendered).

    Returns a NEW dict with ``best_score`` / ``best_latex`` reflecting the
    highest score seen so far. Never mutates ``state``.
    """
    current_score = state.get("aggregate_score")
    current_latex = state.get("latex_rendered", "")
    best_score = state.get("best_score")

    if current_score is None:
        return {}
    if best_score is None or current_score > best_score:
        return {"best_score": current_score, "best_latex": current_latex}
    return {"best_score": best_score, "best_latex": state.get("best_latex", "")}


def bookkeep_node(state: PipelineState) -> dict:
    """Node: update best-scoring draft, then route on pass/fail/cap.

    On a fail that will loop, advances the ``iteration`` counter and resets the
    compile-retry counter here (so the writer sees a fresh compile budget). The
    ``cap_hit`` flag is set when the loop terminates on the iteration cap.
    """
    best = update_best(state)

    passed = bool(state.get("passed", False))
    iteration = state.get("iteration", 1)

    if passed:
        return {**best, "cap_hit": False}
    if iteration >= MAX_ITERATIONS:
        return {**best, "cap_hit": True}
    # Fail and will loop: consume one revision iteration, reset compile budget.
    return {**best, "iteration": iteration + 1, "compile_retries": 0}


# --- conditional-edge functions (pure, independently tested) ------------------


def route_after_identity(state: PipelineState) -> str:
    """violations → ``writer``; clean → ``compile_node``."""
    if state.get("identity_violations"):
        return "writer"
    return "compile_node"


def route_after_compile(state: PipelineState) -> str:
    """ok → ``recruiter_panel``; fail & retries left → ``writer``; else ``emit``.

    The compile-retry budget is ``MAX_COMPILE_RETRIES`` PER iteration and lives
    on ``compile_retries`` — independent of the main ``iteration`` counter.
    """
    if state.get("compile_ok"):
        return "recruiter_panel"
    if state.get("compile_retries", 0) < MAX_COMPILE_RETRIES:
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


def build_graph():
    """Build and compile the pipeline ``StateGraph``.

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
    builder.add_node("writer", write_resume)
    builder.add_node("render_node", render_node)
    builder.add_node("identity_check_node", identity_check_node)
    builder.add_node("compile_node", compile_node)
    builder.add_node("recruiter_panel", recruiter_panel)
    builder.add_node("aggregator", aggregator)
    builder.add_node("bookkeep", bookkeep_node)
    builder.add_node("emit", emit_node)

    # Linear extraction spine.
    builder.add_edge(START, "parse_resume")
    builder.add_edge("parse_resume", "analyze_jd")
    builder.add_edge("analyze_jd", "gap_analysis")
    builder.add_edge("gap_analysis", "writer")

    # Writer → render → identity check.
    builder.add_edge("writer", "render_node")
    builder.add_edge("render_node", "identity_check_node")

    # identity: violations → writer; clean → compile.
    builder.add_conditional_edges(
        "identity_check_node",
        route_after_identity,
        {"writer": "writer", "compile_node": "compile_node"},
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

    builder.add_edge("emit", END)

    return builder.compile()
