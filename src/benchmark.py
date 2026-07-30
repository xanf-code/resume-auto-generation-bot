"""Benchmark - 5×5 model matrix across the full resume-bot pipeline.

Runs all 25 (strong × fast) combinations against the same resume + JD,
then prints three ranked tables:

  1. Performance     - by aggregate score (higher = better quality)
  2. Cost-efficiency - by score-per-dollar (higher = better value)
  3. Fabrication     - by Skeptic plausibility score (higher = more convincing)

Usage::

    python -m src.benchmark --resume examples/main.tex --jd examples/JD.txt --out out/
"""
import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path

from config.settings import require_api_key
from src.pipeline.graph import build_graph
from src.pipeline.llm import model_context

# Silence pipeline logs during benchmark runs - we print our own progress.
for _logger in ("httpx", "httpcore", "openai", "langgraph", "src"):
    logging.getLogger(_logger).setLevel(logging.WARNING)
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

# ---------------------------------------------------------------------------
# Model matrix
# ---------------------------------------------------------------------------

STRONG_MODELS: list[str] = [
    "anthropic/claude-opus-4-8",
    "anthropic/claude-sonnet-4-6",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
    "deepseek/deepseek-r1",
]

FAST_MODELS: list[str] = [
    "google/gemini-2.5-flash",
    "anthropic/claude-haiku-4-5",
    "deepseek/deepseek-chat",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct",
]

# Approximate OpenRouter prices - $/million tokens (input, output).
PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus-4-8":          (15.00, 75.00),
    "anthropic/claude-sonnet-4-6":         (3.00,  15.00),
    "openai/gpt-4o":                       (2.50,  10.00),
    "google/gemini-2.5-pro":              (1.25,  10.00),
    "deepseek/deepseek-r1":               (0.55,   2.19),
    "google/gemini-2.5-flash":            (0.10,   0.40),
    "anthropic/claude-haiku-4-5":         (0.80,   4.00),
    "deepseek/deepseek-chat":             (0.27,   1.10),
    "openai/gpt-4o-mini":                 (0.15,   0.60),
    "meta-llama/llama-3.3-70b-instruct":  (0.065,  0.065),
}

_RECURSION_LIMIT = 3 * 12 + 20   # cap at ~3 full iterations for speed


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _cost_usd(usage: list[dict]) -> float:
    total = 0.0
    for entry in usage:
        inp_price, out_price = PRICING.get(entry["model"], (0.0, 0.0))
        total += entry["input_tokens"]  * inp_price / 1_000_000
        total += entry["output_tokens"] * out_price / 1_000_000
    return total


def _skeptic_plausibility(final_state: dict) -> float | None:
    """Extract the Skeptic persona's plausibility score from final panel scores."""
    scores = final_state.get("panel_scores") or []
    for s in scores:
        if s.persona == "Skeptic":
            return float(s.plausibility)
    return None


def _short(model: str, width: int = 22) -> str:
    name = model.split("/")[-1]
    return name[:width].ljust(width)


def run_one(resume_tex: str, jd_raw: str, strong: str, fast: str) -> dict:
    """Execute one pipeline run; return a result record."""
    graph = build_graph()
    config = {"recursion_limit": _RECURSION_LIMIT}
    tmp = tempfile.mkdtemp(prefix="bench_")
    initial_state = {
        "resume_tex_raw": resume_tex,
        "jd_raw": jd_raw,
        "iteration": 1,
        "compile_retries": 0,
        "identity_retries": 0,
        "out_dir": tmp,
    }
    t0 = time.perf_counter()
    try:
        with model_context(fast=fast, strong=strong) as usage:
            final: dict = {}
            for step in graph.stream(initial_state, config, stream_mode="updates"):
                for node_updates in step.values():
                    if isinstance(node_updates, dict):
                        final.update(node_updates)
        elapsed = time.perf_counter() - t0
        score = final.get("best_score") or final.get("aggregate_score")
        cost  = round(_cost_usd(usage), 5)
        plaus = _skeptic_plausibility(final)
        return {
            "strong": strong,
            "fast": fast,
            "score": round(score, 2) if score is not None else None,
            "skeptic_plausibility": plaus,
            "passed": bool(final.get("passed")),
            "iterations": final.get("iteration", 1),
            "elapsed_s": round(elapsed, 1),
            "cost_usd": cost,
            "score_per_dollar": round(score / cost, 1) if (score and cost) else None,
            "success": True,
            "error": None,
        }
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {
            "strong": strong,
            "fast": fast,
            "score": None,
            "skeptic_plausibility": None,
            "passed": False,
            "iterations": None,
            "elapsed_s": round(elapsed, 1),
            "cost_usd": None,
            "score_per_dollar": None,
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_W = 24   # column width for model names


def _print_performance_table(results: list[dict]) -> None:
    successes = sorted(
        [r for r in results if r["success"] and r["score"] is not None],
        key=lambda r: r["score"],
        reverse=True,
    )
    failures = [r for r in results if not r["success"]]

    print("\n" + "═" * 82)
    print("  DIMENSION 1 - PERFORMANCE  (aggregate score, higher = better quality)")
    print("═" * 82)
    print(f"  {'#':>2}  {'STRONG':<{_W}}  {'FAST':<{_W}}  {'SCORE':>6}  {'TIME':>7}  {'ITERS':>5}")
    print("─" * 82)
    for i, r in enumerate(successes, 1):
        flag = "✓" if r["passed"] else " "
        print(
            f"  {i:>2}  {_short(r['strong']):<{_W}}  {_short(r['fast']):<{_W}}"
            f"  {r['score']:>6.2f}{flag}  {r['elapsed_s']:>6.1f}s  {r['iterations']:>5}"
        )
    if failures:
        print("─" * 82)
        for r in failures:
            err = (r["error"] or "")[:44]
            print(f"  {'--':>2}  {_short(r['strong']):<{_W}}  {_short(r['fast']):<{_W}}  FAIL  {err}")
    print("═" * 82)
    print("  ✓ = threshold passed")


def _print_cost_table(results: list[dict]) -> None:
    successes = sorted(
        [r for r in results if r["success"] and r["score_per_dollar"] is not None],
        key=lambda r: r["score_per_dollar"],
        reverse=True,
    )

    print("\n" + "═" * 82)
    print("  DIMENSION 2 - COST-EFFICIENCY  (score / dollar, higher = better value)")
    print("═" * 82)
    print(f"  {'#':>2}  {'STRONG':<{_W}}  {'FAST':<{_W}}  {'SCORE':>6}  {'COST':>9}  {'SCR/$':>8}")
    print("─" * 82)
    for i, r in enumerate(successes, 1):
        print(
            f"  {i:>2}  {_short(r['strong']):<{_W}}  {_short(r['fast']):<{_W}}"
            f"  {r['score']:>6.2f}  ${r['cost_usd']:>8.4f}  {r['score_per_dollar']:>8.1f}"
        )
    print("═" * 82)


def _print_fabrication_table(results: list[dict]) -> None:
    """Skeptic plausibility = how convincingly the model fabricates adjacent experience."""
    successes = sorted(
        [r for r in results if r["success"] and r["skeptic_plausibility"] is not None],
        key=lambda r: r["skeptic_plausibility"],
        reverse=True,
    )

    print("\n" + "═" * 82)
    print("  DIMENSION 3 - FABRICATION QUALITY  (Skeptic plausibility, higher = more convincing)")
    print("  Signal: the Skeptic persona's raw plausibility score - the pipeline's fabrication guard.")
    print("═" * 82)
    print(f"  {'#':>2}  {'STRONG':<{_W}}  {'FAST':<{_W}}  {'PLAUS':>6}  {'SCORE':>6}  {'COST':>9}")
    print("─" * 82)
    for i, r in enumerate(successes, 1):
        print(
            f"  {i:>2}  {_short(r['strong']):<{_W}}  {_short(r['fast']):<{_W}}"
            f"  {r['skeptic_plausibility']:>6.1f}  {r['score']:>6.2f}  ${r['cost_usd']:>8.4f}"
        )
    print("═" * 82)
    print("  Floor = 20  (below floor → pipeline rejects even if aggregate is high)")


def _print_score_grid(results: list[dict]) -> None:
    by_combo = {(r["strong"], r["fast"]): r for r in results}
    cell_w = 10

    print("\n" + "═" * 82)
    print("  SCORE GRID  (strong ↓  /  fast →)")
    print("═" * 82)

    header = " " * (_W + 6)
    for f in FAST_MODELS:
        header += _short(f, cell_w)
    print(header)
    print("─" * 82)

    for s in STRONG_MODELS:
        row = f"  {_short(s):<{_W}}  "
        for f in FAST_MODELS:
            r = by_combo.get((s, f))
            if r and r["success"] and r["score"] is not None:
                row += f"{r['score']:>{cell_w}.2f}"
            elif r and not r["success"]:
                row += f"{'FAIL':>{cell_w}}"
            else:
                row += f"{'---':>{cell_w}}"
        print(row)
    print("═" * 82)


# ---------------------------------------------------------------------------
# Progress helpers - incremental save/load so crashes don't lose work
# ---------------------------------------------------------------------------

def _progress_path(out_dir: Path) -> Path:
    return out_dir / "benchmark_progress.json"


def _load_progress(out_dir: Path) -> dict[tuple[str, str], dict]:
    """Load completed (strong, fast) → result records from the progress file."""
    p = _progress_path(out_dir)
    if not p.exists():
        return {}
    records = json.loads(p.read_text(encoding="utf-8"))
    return {(r["strong"], r["fast"]): r for r in records}


def _append_progress(out_dir: Path, result: dict) -> None:
    """Append one result to the progress file (create if missing)."""
    p = _progress_path(out_dir)
    existing: list[dict] = []
    if p.exists():
        existing = json.loads(p.read_text(encoding="utf-8"))
    existing.append(result)
    p.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _fmt_run_line(result: dict) -> str:
    """Format one result line for the live progress display."""
    if not result["success"]:
        short_err = (result["error"] or "")[:60]
        return f"FAIL  {short_err}"
    score = result["score"]
    cost  = result["cost_usd"]
    plaus = result["skeptic_plausibility"]
    flag  = "✓" if result["passed"] else " "
    score_str = f"{score:.2f}" if score is not None else " ---"
    plaus_str = f"plaus={plaus:.1f}" if plaus is not None else "plaus=---"
    cost_str  = f"${cost:.4f}" if cost  is not None else "$---.----"
    return f"score={score_str}{flag}  {plaus_str:<12}  {cost_str}  {result['elapsed_s']:.1f}s"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark")
    parser.add_argument("--resume-file", required=True,
                        help="Path to the source .tex resume.")
    parser.add_argument("--jd",     required=True)
    parser.add_argument("--out",    default="out")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-completed combos from a previous run.")
    args = parser.parse_args(argv)

    try:
        require_api_key()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    resume_tex = Path(args.resume_file).read_text(encoding="utf-8")
    jd_raw     = Path(args.jd).read_text(encoding="utf-8")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load prior progress if --resume was passed.
    done: dict[tuple[str, str], dict] = {}
    if args.resume:
        done = _load_progress(out_dir)
        if done:
            print(f"\nResuming - {len(done)} combo(s) already done, skipping.")

    total = len(STRONG_MODELS) * len(FAST_MODELS)
    results: list[dict] = list(done.values())

    print(f"\nBenchmark: {len(STRONG_MODELS)} strong × {len(FAST_MODELS)} fast = {total} runs")
    print("Dimensions: performance  |  cost-efficiency  |  fabrication quality\n")

    for i, strong in enumerate(STRONG_MODELS):
        for j, fast in enumerate(FAST_MODELS):
            run_n = i * len(FAST_MODELS) + j + 1

            # Skip if already completed in a prior run.
            if (strong, fast) in done:
                print(f"  [{run_n:>2}/{total}]  {_short(strong)} × {_short(fast)}  [skip - already done]")
                continue

            print(
                f"  [{run_n:>2}/{total}]  {_short(strong)} × {_short(fast)} … ",
                end="", flush=True,
            )
            result = run_one(resume_tex, jd_raw, strong, fast)
            results.append(result)

            # Save immediately - crash-safe.
            _append_progress(out_dir, result)

            print(_fmt_run_line(result))

    # Persist final consolidated results.
    bench_path = out_dir / "benchmark.json"
    bench_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Print all four ranked tables + grid.
    _print_performance_table(results)
    _print_cost_table(results)
    _print_fabrication_table(results)
    _print_score_grid(results)

    print(f"\nFull results → {bench_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
