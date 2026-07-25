"""Tests for src.batch - batch runner cost optimization (parse-once caching).

``run_batch`` used to re-invoke the parser LLM once per JD subprocess even
though every job in a batch shares the SAME resume - pure duplicate cost with
zero benefit. These tests pin that the resume is now parsed exactly ONCE for
the whole batch and the resulting struct/ledger are threaded through every
job, regardless of job count.

No real ``ProcessPoolExecutor``/subprocesses are used - a small in-process
fake stands in so the tests stay hermetic and fast (see ``_FakeExecutor``).
"""
from unittest.mock import patch

from src import batch


class _FakeFuture:
    """Minimal stand-in for concurrent.futures.Future - no subprocess involved."""

    def __init__(self, value=None, exc=None):
        self._value = value
        self._exc = exc

    def result(self):
        if self._exc is not None:
            raise self._exc
        return self._value


class _FakeExecutor:
    """Runs submitted work synchronously in-process (no real subprocesses)."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def submit(self, fn, *args, **kwargs):
        try:
            return _FakeFuture(value=fn(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 - mirrors real executor semantics
            return _FakeFuture(exc=exc)


def _fake_as_completed(future_to_label):
    return iter(future_to_label.keys())


def _canned_result(job_label: str, jd_path: str, out_dir: str) -> dict:
    return {
        "label": job_label,
        "jd_path": jd_path,
        "out_dir": out_dir,
        "passed": True,
        "cap_hit": False,
        "best_score": 90.0,
        "output_pdf": f"{out_dir}/out.pdf",
        "output_report": f"{out_dir}/report.json",
        "error": None,
    }


# --- run_batch: resume parsed exactly once ------------------------------------


def test_run_batch_parses_resume_exactly_once(tmp_path, monkeypatch):
    """N JDs against the same resume must trigger exactly ONE parse call."""
    resume = tmp_path / "resume.tex"
    resume.write_text(r"\documentclass{article}\begin{document}\end{document}")

    jd_paths = []
    for i in range(3):
        jd = tmp_path / f"jd{i}.txt"
        jd.write_text(f"JD {i}")
        jd_paths.append(str(jd))

    parse_calls = {"n": 0}
    fake_struct = object()
    fake_ledger = object()

    def fake_parse_resume(state):
        parse_calls["n"] += 1
        assert "resume_tex_raw" in state
        return {"resume_struct": fake_struct, "identity_ledger": fake_ledger}

    run_single_calls = []

    def fake_run_single(resume_path, jd_path, out_dir, job_label, resume_struct=None, identity_ledger=None):
        run_single_calls.append((resume_struct, identity_ledger))
        return _canned_result(job_label, jd_path, out_dir)

    monkeypatch.setattr(batch, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(batch, "_run_single", fake_run_single)
    monkeypatch.setattr(batch, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(batch, "as_completed", _fake_as_completed)

    results = batch.run_batch(str(resume), jd_paths, str(tmp_path / "out"), max_workers=3)

    assert parse_calls["n"] == 1, "resume must be parsed exactly once for the whole batch, not once per JD"
    assert len(run_single_calls) == 3
    for rs, il in run_single_calls:
        assert rs is fake_struct
        assert il is fake_ledger
    assert len(results) == 3


def test_run_batch_parses_once_even_for_a_single_job(tmp_path, monkeypatch):
    """Sanity: the parse-once behaviour holds even for a batch of one JD."""
    resume = tmp_path / "resume.tex"
    resume.write_text(r"\documentclass{article}\begin{document}\end{document}")
    jd = tmp_path / "jd.txt"
    jd.write_text("JD")

    parse_calls = {"n": 0}

    def fake_parse_resume(state):
        parse_calls["n"] += 1
        return {"resume_struct": object(), "identity_ledger": object()}

    monkeypatch.setattr(batch, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(
        batch, "_run_single",
        lambda r, j, o, lbl, resume_struct=None, identity_ledger=None: _canned_result(lbl, j, o),
    )
    monkeypatch.setattr(batch, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(batch, "as_completed", _fake_as_completed)

    batch.run_batch(str(resume), [str(jd)], str(tmp_path / "out"), max_workers=1)

    assert parse_calls["n"] == 1


# --- _run_single: forwards the cached struct/ledger into src.main.run --------


def test_run_single_forwards_cached_struct_and_ledger(tmp_path):
    fake_struct = object()
    fake_ledger = object()
    captured = {}

    def fake_main_run(resume_path, jd_path, out_dir, resume_struct=None, identity_ledger=None):
        captured["resume_struct"] = resume_struct
        captured["identity_ledger"] = identity_ledger
        return {
            "passed": True, "cap_hit": False, "best_score": 90.0,
            "output_pdf": "x.pdf", "output_report": "r.json",
        }

    with patch("src.main.run", side_effect=fake_main_run):
        result = batch._run_single(
            "resume.tex", "jd.txt", str(tmp_path), "jd_01",
            resume_struct=fake_struct, identity_ledger=fake_ledger,
        )

    assert captured["resume_struct"] is fake_struct
    assert captured["identity_ledger"] is fake_ledger
    assert result["passed"] is True


def test_run_single_still_works_without_cached_struct(tmp_path):
    """Backward compatible: resume_struct/identity_ledger default to None and
    are forwarded as None, preserving the original (non-batch) parse path."""
    def fake_main_run(resume_path, jd_path, out_dir, resume_struct=None, identity_ledger=None):
        assert resume_struct is None
        assert identity_ledger is None
        return {
            "passed": False, "cap_hit": True, "best_score": 50.0,
            "output_pdf": None, "output_report": "r.json",
        }

    with patch("src.main.run", side_effect=fake_main_run):
        result = batch._run_single("resume.tex", "jd.txt", str(tmp_path), "jd_01")

    assert result["passed"] is False
    assert result["cap_hit"] is True


def test_run_single_error_path_unaffected(tmp_path):
    """Existing error-handling behaviour must survive the signature change."""
    with patch("src.main.run", side_effect=ValueError("ledger drift")):
        result = batch._run_single("resume.tex", "jd.txt", str(tmp_path), "jd_01")

    assert result["passed"] is False
    assert result["error"] == "ValueError: ledger drift"
