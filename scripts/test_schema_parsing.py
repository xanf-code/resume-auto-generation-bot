"""Schema-compliance tester for the scoring role - the exact call path that
surfaced the deepseek/deepseek-v4-flash malformed-JSON failure.

Fires the real ATS_MATCHER_SYSTEM persona prompt at one or more candidate
models N times each, via the same ``parse_scoring`` entrypoint the recruiter
panel uses in production, and reports the pass rate. Use this to vet a
scoring model before wiring it into the web UI, without spending a full
pipeline run (parse -> analyze -> gap -> writer -> compile -> panel) per model.

Usage::

    python -m scripts.test_schema_parsing --model deepseek/deepseek-v4-flash --runs 10
    python -m scripts.test_schema_parsing --model openai/gpt-4o-mini --model z-ai/glm-5.2 --runs 5

    # Test whether enabling reasoning or a lower temperature changes reliability:
    python -m scripts.test_schema_parsing --model deepseek/deepseek-v4-flash \\
        --runs 10 --effort high --temperature 0.0

    # Supply pricing for a model not in benchmark.py's PRICING table (required
    # for cost to show as anything but "n/a" - $/million tokens):
    python -m scripts.test_schema_parsing --model deepseek/deepseek-v4-flash \\
        --runs 10 --price-in 0.20 --price-out 0.80
"""
import argparse
import time

from pydantic import ValidationError

from src.pipeline.llm import model_context, parse_scoring
from src.pipeline.schemas import PanelScore
from src.prompts.recruiters import ATS_MATCHER_SYSTEM

# $/million tokens (input, output). Only models already priced elsewhere in
# this codebase (see src/benchmark.py's PRICING table) - deliberately NOT
# extended with guessed numbers for models like deepseek/deepseek-v4-flash or
# z-ai/glm-5.2 that aren't vetted here. Use --price-in/--price-out to supply
# a rate for any model not listed; unpriced + no override prints "n/a".
_KNOWN_PRICING: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
}

# A short, representative rendered-resume + JD-vector pair - enough surface
# area to exercise the real persona prompt without the cost of a full pipeline
# run. Swap in real content from examples/ if you want to test against a
# specific resume/JD combination instead.
_SAMPLE_LATEX = r"""
\resumeSubheading{Software Engineer}{Jan 2022 -- Present}{Acme Corp}{Remote}
\resumeItemListStart
\resumeItem{Built a Python/Airflow pipeline consolidating 4 reporting systems, dropping monthly close from 5 days to 2, and cut ingest latency 38\% by batching Kafka consumer commits}
\resumeItem{Migrated a monolith's auth layer to a Node.js/Express microservice behind an API gateway, reducing login p95 latency from 900ms to 210ms across 3 environments}
\resumeItem{Instrumented services with OpenTelemetry spans and a Prometheus scrape endpoint, cutting mean time-to-detect latency regressions from 2 hours to 8 minutes}
\resumeItemListEnd
"""

_SAMPLE_JD_VECTOR = """{
  "weighted_skills": [
    {"name": "Python", "weight": 1.0},
    {"name": "Kafka", "weight": 0.9},
    {"name": "AWS", "weight": 0.8},
    {"name": "system design", "weight": 0.7}
  ],
  "ats_keywords": ["Python", "Kafka", "AWS", "REST APIs", "CI/CD"],
  "seniority": "mid",
  "must_mirror": ["Experience with Python and distributed systems"],
  "duty_verbs": ["instrument services with telemetry", "build data pipelines"]
}"""

_USER_MESSAGE = (
    "## RENDERED RESUME (LaTeX)\n" + _SAMPLE_LATEX + "\n\n"
    "## JOB DESCRIPTION (vector)\n" + _SAMPLE_JD_VECTOR + "\n"
)

# Sentinel distinguishing "flag not passed - use role default" from an
# explicit override. Needed because model_context's own _UNSET/None split is
# meaningful: effort=None explicitly SUPPRESSES the reasoning param (for
# providers that reject it), while omitting the kwarg entirely lets the role
# default (no reasoning, for MODEL_SCORING) take over. This script must not
# collapse "not requested" and "explicitly disabled" into the same case.
_NOT_SET = object()


def _cost_usd(
    model: str, usage: list[dict], price_override: tuple[float, float] | None
) -> float | None:
    """Cost of one call in USD, or None if no pricing is known for *model*.

    *price_override* (input, output) $/million tokens takes precedence over
    ``_KNOWN_PRICING``; returns None (not 0.0) when neither is available so
    callers don't silently report a fabricated free call.
    """
    prices = price_override or _KNOWN_PRICING.get(model)
    if prices is None:
        return None
    price_in, price_out = prices
    total = 0.0
    for entry in usage:
        total += entry["input_tokens"] * price_in / 1_000_000
        total += entry["output_tokens"] * price_out / 1_000_000
    return total


def run_once(
    model: str,
    effort: str | None = _NOT_SET,
    temperature: float | None = _NOT_SET,
    price_override: tuple[float, float] | None = None,
) -> tuple[bool, str, float | None, float]:
    """One scoring call against *model* through the real parse_scoring path.

    ``effort``/``temperature`` mirror model_context's own semantics: pass the
    string "none" to explicitly disable reasoning, a depth like "high" to
    enable it, or leave unset (_NOT_SET, the default) to use the role default.

    Returns ``(ok, detail, cost_usd, elapsed_seconds)`` - detail is either the
    parsed score summary or the exception type/message, truncated for
    terminal display; cost_usd is None when pricing for *model* is unknown
    (see _cost_usd). elapsed_seconds is timed even on failure - a model that
    fails fast is a different tradeoff than one that hangs before failing.
    """
    context_kwargs: dict = {
        "fast": "openai/gpt-4o-mini", "strong": "openai/gpt-4o-mini", "scoring": model,
    }
    if effort is not _NOT_SET:
        context_kwargs["effort_scoring"] = effort
    if temperature is not _NOT_SET:
        context_kwargs["temp_scoring"] = temperature

    # Bound before the try so a mid-call parse failure still has a (partial)
    # usage list to cost - the API call is billed before structured-output
    # parsing runs, so a malformed-JSON failure is NOT a free call.
    usage: list[dict] = []
    t0 = time.perf_counter()
    try:
        with model_context(**context_kwargs) as usage:
            score = parse_scoring(ATS_MATCHER_SYSTEM, _USER_MESSAGE, PanelScore)
        elapsed = time.perf_counter() - t0
        detail = (
            f"km={score.keyword_match} iq={score.impact_quality} "
            f"coh={score.coherence} plaus={score.plausibility} fmt={score.formatting}"
        )
        return True, detail, _cost_usd(model, usage, price_override), elapsed
    except ValidationError as e:
        elapsed = time.perf_counter() - t0
        return False, f"ValidationError: {e}", _cost_usd(model, usage, price_override), elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return False, f"{type(e).__name__}: {e}", _cost_usd(model, usage, price_override), elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", action="append", required=True,
        help="OpenRouter model id to test (repeatable)",
    )
    parser.add_argument(
        "--runs", type=int, default=5,
        help="Calls per model - structured-output failures are often "
        "stochastic, not deterministic (default: 5)",
    )
    parser.add_argument(
        "--effort", default=None,
        help="Reasoning effort for the scoring call (e.g. low/medium/high/xhigh/max, "
        "or the literal string 'none' to explicitly disable reasoning). "
        "Omit entirely to use the role default (no reasoning).",
    )
    parser.add_argument(
        "--temperature", type=float, default=None,
        help="Sampling temperature for the scoring call (e.g. 0.0-1.0). "
        "Omit entirely to use the provider default.",
    )
    parser.add_argument(
        "--price-in", type=float, default=None,
        help="$/million input tokens for models not in the built-in pricing "
        "table (e.g. deepseek/deepseek-v4-flash). Must be paired with --price-out.",
    )
    parser.add_argument(
        "--price-out", type=float, default=None,
        help="$/million output tokens - see --price-in.",
    )
    args = parser.parse_args()

    if (args.price_in is None) != (args.price_out is None):
        parser.error("--price-in and --price-out must be supplied together")
    price_override = (
        (args.price_in, args.price_out) if args.price_in is not None else None
    )

    effort = args.effort if args.effort is not None else _NOT_SET
    temperature = args.temperature if args.temperature is not None else _NOT_SET

    for model in args.model:
        passes = 0
        total_cost = 0.0
        any_unpriced = False
        elapsed_times: list[float] = []
        print(f"\n=== {model}  (effort={args.effort or 'default'}, "
              f"temp={args.temperature if args.temperature is not None else 'default'}) ===")
        for i in range(args.runs):
            ok, detail, cost, elapsed = run_once(
                model, effort=effort, temperature=temperature, price_override=price_override
            )
            status = "PASS" if ok else "FAIL"
            cost_str = f"${cost:.5f}" if cost is not None else "n/a"
            if cost is None:
                any_unpriced = True
            else:
                total_cost += cost
            elapsed_times.append(elapsed)
            print(
                f"  [{i + 1}/{args.runs}] {status}  cost={cost_str}  "
                f"time={elapsed:.2f}s  {detail[:200]}"
            )
            passes += ok
        cost_summary = f"${total_cost:.5f}" + (" (partial - some calls unpriced)" if any_unpriced else "")
        avg_time = sum(elapsed_times) / len(elapsed_times)
        print(
            f"  -> {passes}/{args.runs} passed, total cost {cost_summary}, "
            f"avg time {avg_time:.2f}s (min {min(elapsed_times):.2f}s, max {max(elapsed_times):.2f}s)"
        )


if __name__ == "__main__":
    main()
