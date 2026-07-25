"""Batch runner - process multiple JDs against one resume in parallel.

Usage::

    python -m src.batch \\
        --resume examples/main.tex \\
        --jds path/to/jd1.txt path/to/jd2.txt ... \\
        --out out/batch \\
        --workers 4

Each JD gets its own isolated output subdirectory (``out/batch/jd_01/``, etc.).
A ``batch_summary.json`` is written to the root output dir when all runs finish.

Worker count defaults to min(len(jds), 4) - stay under OpenRouter rate limits.
Bump ``--workers`` at your own risk if you have a high-tier API plan.
"""
import argparse
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

log = logging.getLogger(__name__)

from src.agents.parser import parse_resume
from src.pipeline.schemas import IdentityLedger, ResumeStruct


# ---------------------------------------------------------------------------
# Worker - runs in a subprocess, so it must be a top-level importable fn
# ---------------------------------------------------------------------------

def _run_single(
    resume_path: str,
    jd_path: str,
    out_dir: str,
    job_label: str,
    resume_struct: ResumeStruct | None = None,
    identity_ledger: IdentityLedger | None = None,
) -> dict:
    """Execute one pipeline run. Designed to be called in a subprocess.

    ``resume_struct``/``identity_ledger`` are the batch-wide parse-once result
    (see ``_parse_resume_once``) - forwarded through so this job's pipeline run
    skips its own parser LLM call.
    """
    import logging as _log_mod
    _log_mod.basicConfig(
        level=_log_mod.INFO,
        format=f"[{job_label}] %(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    from src.main import run
    try:
        state = run(
            resume_path, jd_path, out_dir,
            resume_struct=resume_struct, identity_ledger=identity_ledger,
        )
        return {
            "label":       job_label,
            "jd_path":     jd_path,
            "out_dir":     out_dir,
            "passed":      bool(state.get("passed")),
            "cap_hit":     bool(state.get("cap_hit")),
            "best_score":  state.get("best_score"),
            "output_pdf":  state.get("output_pdf"),
            "output_report": state.get("output_report"),
            "error":       None,
        }
    except Exception as exc:
        return {
            "label":       job_label,
            "jd_path":     jd_path,
            "out_dir":     out_dir,
            "passed":      False,
            "cap_hit":     False,
            "best_score":  None,
            "output_pdf":  None,
            "output_report": None,
            "error":       f"{type(exc).__name__}: {exc}",
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _parse_resume_once(resume_path: str) -> tuple[ResumeStruct, IdentityLedger]:
    """Parse the resume ONE time; every JD job in the batch reuses the result.

    ``run_batch`` fans one resume out to N JD subprocesses, each of which used
    to re-invoke the parser LLM on the identical resume text - pure duplicate
    cost for zero benefit. Parsing once here in the parent process and passing
    the result into every job removes that duplication.
    """
    resume_tex_raw = Path(resume_path).read_text(encoding="utf-8")
    parsed = parse_resume({"resume_tex_raw": resume_tex_raw})
    return parsed["resume_struct"], parsed["identity_ledger"]


def run_batch(
    resume_path: str,
    jd_paths: list[str],
    out_root: str,
    max_workers: int,
) -> list[dict]:
    """Dispatch all JDs to a process pool and collect results."""
    out_root_p = Path(out_root)
    out_root_p.mkdir(parents=True, exist_ok=True)

    resume_struct, identity_ledger = _parse_resume_once(resume_path)

    jobs: list[tuple[str, str, str, str]] = []
    for idx, jd_path in enumerate(jd_paths, start=1):
        label = f"jd_{idx:02d}"
        out_dir = str(out_root_p / label)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        jobs.append((resume_path, jd_path, out_dir, label))

    results: list[dict] = []
    workers = min(max_workers, len(jobs))
    print(f"\nBatch: {len(jobs)} JDs - {workers} parallel workers\n" + "─" * 52)

    with ProcessPoolExecutor(max_workers=workers) as pool:
        future_to_label = {
            pool.submit(_run_single, r, j, o, lbl, resume_struct, identity_ledger): lbl
            for r, j, o, lbl in jobs
        }
        for fut in as_completed(future_to_label):
            label = future_to_label[fut]
            try:
                result = fut.result()
            except Exception as exc:
                result = {
                    "label": label,
                    "error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                }
            results.append(result)
            status = "✓ PASS" if result.get("passed") else ("⚠ CAP" if result.get("cap_hit") else "✗ FAIL")
            score = f"score={result.get('best_score', '?'):.2f}" if result.get("best_score") is not None else ""
            err = f"  ERROR: {result['error']}" if result.get("error") else ""
            print(f"  {label}  {status}  {score}{err}")

    # Sort results back into submission order for a stable summary
    label_order = {j[3]: i for i, j in enumerate(jobs)}
    results.sort(key=lambda r: label_order.get(r["label"], 999))
    return results


def write_summary(results: list[dict], out_root: str) -> Path:
    summary_path = Path(out_root) / "batch_summary.json"
    summary = {
        "total":  len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "cap_hit": sum(1 for r in results if r.get("cap_hit") and not r.get("passed")),
        "failed": sum(1 for r in results if not r.get("passed") and not r.get("cap_hit")),
        "runs":   results,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resume-bot-batch",
        description="Run resume-bot against multiple JDs in parallel.",
    )
    p.add_argument("--resume", required=True, help="Source .tex resume path.")
    p.add_argument("--jds", nargs="+", required=True, help="One or more JD .txt paths.")
    p.add_argument("--out", default="out/batch", help="Root output directory.")
    p.add_argument(
        "--workers", type=int, default=4,
        help="Max parallel workers (default 4 - safe for standard API tier).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    args = build_parser().parse_args(argv)

    jd_paths = args.jds
    if not jd_paths:
        print("error: no JD files provided.", file=sys.stderr)
        return 2

    missing = [p for p in jd_paths if not Path(p).is_file()]
    if missing:
        for m in missing:
            print(f"error: JD file not found: {m}", file=sys.stderr)
        return 2

    results = run_batch(args.resume, jd_paths, args.out, args.workers)
    summary_path = write_summary(results, args.out)

    passed = sum(1 for r in results if r.get("passed"))
    print(f"\n{'='*52}")
    print(f"Batch complete: {passed}/{len(results)} passed")
    print(f"Summary: {summary_path}")
    print("=" * 52)

    return 0 if passed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
