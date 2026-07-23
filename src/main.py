"""CLI entry point — run the resume-optimization pipeline end-to-end.

Usage::

    python -m src.main --resume examples/sample_resume.tex \\
        --jd examples/sample_jd.txt --out out/

Fails fast (before any LLM call) if ``ANTHROPIC_API_KEY`` is missing. Reads the
resume/JD files into the initial state, invokes the compiled graph, streams
per-iteration progress to stdout, and writes outputs via the emit node.
"""
import argparse
import sys
from pathlib import Path

from config.settings import MAX_ITERATIONS, require_api_key
from src.pipeline.graph import build_graph

# LangGraph recursion budget: each revision iteration traverses several nodes
# (writer → render → identity → compile → panel → aggregator → bookkeep), and
# compile retries add more hops. Give ample headroom above the worst case.
_RECURSION_LIMIT = MAX_ITERATIONS * 12 + 20

_PERSONA_ORDER = ("ATS Matcher", "Hiring Manager", "Technical Screener", "Skeptic")


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


def run(resume_path: str, jd_path: str, out_dir: str) -> dict:
    """Execute the pipeline. Requires the API key (fires the fail-fast gate)."""
    require_api_key()  # fail fast before any node runs

    resume_tex_raw = _read_text(resume_path)
    jd_raw = _read_text(jd_path)

    initial_state = {
        "resume_tex_raw": resume_tex_raw,
        "jd_raw": jd_raw,
        "iteration": 1,
        "compile_retries": 0,
        "out_dir": out_dir,
    }

    graph = build_graph()
    config = {"recursion_limit": _RECURSION_LIMIT}

    final_state: dict = {}
    last_printed_agg: float | None = None  # deduplicate: only print on fresh aggregate
    print("Running resume-bot pipeline…")
    for step in graph.stream(initial_state, config, stream_mode="updates"):
        # stream_mode="updates" gives only the dict of changed keys per node.
        # Merge into final_state manually so we always have the full picture.
        final_state.update(step)
        # Only print when the aggregator just wrote a new aggregate_score.
        if "aggregate_score" in step:
            agg = final_state.get("aggregate_score")
            if agg != last_printed_agg:
                last_printed_agg = agg
                _print_progress(final_state)

    _print_summary(final_state)
    return final_state


def _print_summary(state: dict) -> None:
    """Print the terminal summary (outcome + output paths)."""
    print("\n" + "=" * 52)
    if state.get("passed"):
        print("RESULT: PASSED — threshold cleared.")
    elif state.get("cap_hit"):
        print("RESULT: CAP HIT — emitting BEST-scoring draft (see warning).")
    else:
        print("RESULT: FAILED — no passing draft produced.")

    if state.get("best_score") is not None:
        print(f"Best aggregate score: {state['best_score']:.2f}")
    pdf = state.get("output_pdf")
    report = state.get("output_report")
    print(f"PDF:    {pdf if pdf else '(none — compile never succeeded)'}")
    print(f"Report: {report}")
    print("=" * 52)


def main(argv: list[str] | None = None) -> int:
    """CLI main. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        state = run(args.resume, args.jd, args.out)
    except RuntimeError as exc:  # missing API key — clear, fail-fast message.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    # Exit non-zero when no acceptable draft was produced.
    return 0 if state.get("passed") or state.get("output_pdf") else 1


if __name__ == "__main__":
    raise SystemExit(main())
