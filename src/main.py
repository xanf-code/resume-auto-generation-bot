"""CLI entry point - run the resume-optimization pipeline end-to-end.

Usage::

    python -m src.main --resume examples/sample_resume.tex \\
        --jd examples/sample_jd.txt --out out/

Fails fast (before any LLM call) if ``OPENROUTER_API_KEY`` is missing. Reads the
resume/JD files into the initial state, invokes the compiled graph, streams
per-iteration progress to stdout, and writes outputs via the emit node.

Outputs are packaged per-JD: a run against ``examples/JD1.txt`` writes
``out/JD1/`` containing ``resume.pdf``, ``score_report.json``, and ``skills.json``.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Callable

from config.settings import MAX_ITERATIONS, require_api_key
from src.pipeline.graph import build_graph
from src.pipeline.schemas import IdentityLedger, ResumeStruct
from src.pipeline.tuning import PipelineTuning

# ---------------------------------------------------------------------------
# Logging - configured once here; every module uses getLogger(__name__)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger(__name__)

# Silence noisy third-party loggers.
for _noisy in ("httpx", "httpcore", "anthropic", "langgraph"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# LangGraph recursion budget: each revision iteration traverses several nodes
# (writer → render → identity → compile → panel → aggregator → bookkeep), and
# compile retries add more hops. ``stream_pipeline`` computes the limit from the
# run's ``max_iterations`` (default or tuned) so a larger loop budget scales the
# headroom with it - see the ``recursion_limit`` there.

_PERSONA_ORDER = ("ATS Matcher", "Hiring Manager", "Technical Screener", "Skeptic")

# Maps a distinctive state key to the node that wrote it - used to label
# stream steps when printing per-node progress to stdout.
_KEY_TO_NODE: dict[str, str] = {
    "identity_ledger":    "parse_resume",
    "jd_vector":          "analyze_jd",
    "gap_targets":        "gap_analysis",
    "skill_dump":         "generate_skills",
    "writer_output":      "writer",
    "latex_rendered":     "render",
    "identity_violations":"identity_check",
    "compile_ok":         "compile",
    "panel_scores":       "recruiter_panel",
    "aggregate_score":    "aggregator",
    "best_score":         "bookkeep",
    "cap_hit":            "bookkeep",
    "output_pdf":         "emit",
    "output_skills":      "emit",
    "score_report_md":    "score_report",
}


def _read_text(path: str) -> str:
    """Read a UTF-8 text file, failing clearly if it is missing."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    return p.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser (no side effects, no key needed)."""
    parser = argparse.ArgumentParser(
        prog="resume-bot",
        description="Tailor a LaTeX resume to a target job description.",
    )
    parser.add_argument("--resume", required=True, help="Path to the source .tex resume.")
    parser.add_argument("--jd", required=True, help="Path to the target job description (.txt).")
    parser.add_argument("--out", default="out", help="Output directory (default: out/).")
    parser.add_argument(
        "--score",
        action="store_true",
        default=False,
        help=(
            "Deprecated no-op. Persona panel scoring (score_report.json) always "
            "runs; resume_scorer is not invoked."
        ),
    )
    return parser


def _print_progress(state: dict) -> None:
    """Stream one node's per-iteration progress to stdout.

    Prints a compact scoreboard whenever a fresh aggregate is available.
    """
    scores = state.get("panel_scores") or []
    if not scores:
        return
    agg = state.get("aggregate_score")
    passed = state.get("passed")
    iteration = state.get("iteration", "?")

    by_persona = {s.persona: s for s in scores}
    print(f"\n── iteration {iteration} " + "─" * 40)
    for name in _PERSONA_ORDER:
        s = by_persona.get(name)
        if s is None:
            continue
        print(
            f"  {name:<20} km={s.keyword_match:>3} iq={s.impact_quality:>3} "
            f"coh={s.coherence:>3} plaus={s.plausibility:>3} fmt={s.formatting:>3}"
        )
    verdict = "PASS" if passed else "fail"
    if agg is not None:
        print(f"  aggregate = {agg:.2f}   →   {verdict}")


def stream_pipeline(
    resume_tex_raw: str,
    jd_raw: str,
    out_dir: str,
    jd_name: str,
    enable_scoring: bool = False,
    resume_struct: ResumeStruct | None = None,
    identity_ledger: IdentityLedger | None = None,
    on_step: Callable[[dict, dict], None] | None = None,
    tuning: PipelineTuning | None = None,
) -> dict:
    """Run the pipeline from raw content, streaming per-node progress.

    Content-based, callback-driven core shared by the CLI (:func:`run`) and the
    web layer. Accepts the resume/JD as in-memory strings (no file paths), calls
    :func:`require_api_key` first (fail-fast, before any node runs), then streams
    the compiled graph. ``on_step(flat_delta, accumulated_state)`` - when given -
    is invoked once per streamed node with that node's state delta and the
    running accumulated state. Does no file I/O and prints nothing; returns the
    accumulated ``final_state``.

    ``resume_struct``/``identity_ledger`` let a caller that already parsed this
    exact resume (e.g. batch mode, running one resume against many JDs) skip
    the parser LLM call - ``parse_resume`` short-circuits when both are seeded.

    ``tuning`` - when given - carries per-run knobs (threshold, floor, loop/retry
    budgets, rubric weights) onto the state so nodes read them instead of the
    ``config.settings`` defaults. The LangGraph recursion budget scales off the
    run's ``max_iterations`` so a larger loop budget doesn't trip the limit.
    """
    require_api_key()  # fail fast before any node runs

    effective_tuning = tuning if tuning is not None else PipelineTuning.defaults()

    initial_state: dict = {
        "resume_tex_raw": resume_tex_raw,
        "jd_raw": jd_raw,
        "iteration": 1,
        "compile_retries": 0,
        "identity_retries": 0,
        "out_dir": out_dir,
        "jd_name": jd_name,
        "enable_scoring": enable_scoring,
        "tuning": effective_tuning,
    }
    if resume_struct is not None:
        initial_state["resume_struct"] = resume_struct
    if identity_ledger is not None:
        initial_state["identity_ledger"] = identity_ledger

    graph = build_graph(enable_scoring=enable_scoring)
    recursion_limit = effective_tuning.max_iterations * 12 + 20
    config = {"recursion_limit": recursion_limit}

    final_state: dict = {}
    for step in graph.stream(initial_state, config, stream_mode="updates"):
        # stream_mode="updates" yields {node_name: {state_updates}} - flatten one level.
        flat: dict = {}
        for node_updates in step.values():
            if isinstance(node_updates, dict):
                flat.update(node_updates)
        final_state.update(flat)
        if on_step is not None:
            on_step(flat, final_state)
    return final_state


def _stdout_step_printer() -> Callable[[dict, dict], None]:
    """Build the CLI's per-node progress printer (stateful over the run)."""
    last_printed_agg: list[float | None] = [None]

    def on_step(flat: dict, final_state: dict) -> None:
        # Identify which node just ran by matching a known state key.
        node_name = next((v for k, v in _KEY_TO_NODE.items() if k in flat), None)
        if node_name:
            log.info("─── node: %-18s keys=%s", node_name, list(flat.keys()))
        # Print the full scoreboard only when a fresh aggregate arrives.
        if "aggregate_score" in flat:
            agg = final_state.get("aggregate_score")
            if agg != last_printed_agg[0]:
                last_printed_agg[0] = agg
                _print_progress(final_state)

    return on_step


def run(
    resume_path: str,
    jd_path: str,
    out_dir: str,
    enable_scoring: bool = False,
    resume_struct: ResumeStruct | None = None,
    identity_ledger: IdentityLedger | None = None,
) -> dict:
    """Execute the pipeline from files (CLI path). Fail-fast on missing API key.

    Thin wrapper over :func:`stream_pipeline`: reads the resume/JD files, streams
    the pipeline while printing per-iteration progress to stdout, then prints the
    terminal summary.
    """
    require_api_key()  # fail fast before any node runs (before file I/O too)

    resume_tex_raw = _read_text(resume_path)
    jd_raw = _read_text(jd_path)

    log.info("main         | pipeline starting - max_iterations=%d", MAX_ITERATIONS)
    print("Running resume-bot pipeline…")

    final_state = stream_pipeline(
        resume_tex_raw,
        jd_raw,
        out_dir=out_dir,
        jd_name=Path(jd_path).stem,
        enable_scoring=enable_scoring,
        resume_struct=resume_struct,
        identity_ledger=identity_ledger,
        on_step=_stdout_step_printer(),
    )

    _print_summary(final_state)
    return final_state


def _print_summary(state: dict) -> None:
    """Print the terminal summary (outcome + output paths)."""
    print("\n" + "=" * 52)
    if state.get("passed"):
        print("RESULT: PASSED - threshold cleared.")
    elif state.get("cap_hit"):
        print("RESULT: CAP HIT - emitting BEST-scoring draft (see warning).")
    else:
        print("RESULT: FAILED - no passing draft produced.")

    if state.get("best_score") is not None:
        print(f"Best aggregate score: {state['best_score']:.2f}")
    pdf = state.get("output_pdf")
    report = state.get("output_report")
    skills = state.get("output_skills")
    score_md = state.get("score_report_md")
    if report:
        print(f"Package:      {Path(report).parent}/")
    print(f"PDF:          {pdf if pdf else '(none - compile never succeeded)'}")
    print(f"Score Report: {report}")
    print(f"Skills JSON:  {skills}")
    if score_md:
        print(f"Score MD:     {score_md}")
    print("=" * 52)


try:
    from langgraph.errors import GraphRecursionError as _GraphRecursionError
except ImportError:
    _GraphRecursionError = None


def main(argv: list[str] | None = None) -> int:
    """CLI main. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        state = run(args.resume, args.jd, args.out, enable_scoring=args.score)
    except Exception as exc:
        # GraphRecursionError subclasses RuntimeError - check it first.
        if _GraphRecursionError is not None and isinstance(exc, _GraphRecursionError):
            print(
                "error: pipeline recursion limit exceeded - the identity or compile "
                "loop ran without converging. Check your resume for unusual LaTeX "
                "formatting.",
                file=sys.stderr,
            )
            log.error("unhandled exception in pipeline", exc_info=True)
            return 1
        if isinstance(exc, RuntimeError):  # missing API key - clear, fail-fast message.
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if isinstance(exc, FileNotFoundError):
            print(f"error: {exc}", file=sys.stderr)
            return 2
        log.error("unhandled exception in pipeline", exc_info=True)
        print(
            f"error: unexpected failure - {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    # Exit non-zero when no acceptable draft was produced.
    return 0 if state.get("passed") or state.get("output_pdf") else 1


if __name__ == "__main__":
    raise SystemExit(main())
