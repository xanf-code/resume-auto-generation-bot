"""Tests for src.main CLI entry point — exception handling and exit codes."""
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_ARGV = ["--resume", "r.tex", "--jd", "jd.txt", "--out", "out"]


def _run_main(argv=None):
    """Call main() and return the exit code."""
    from src.main import main
    return main(argv or _FAKE_ARGV)


# ---------------------------------------------------------------------------
# Existing exception types (must still return 2)
# ---------------------------------------------------------------------------

def test_main_returns_2_on_runtime_error():
    """RuntimeError (missing API key) must return exit code 2."""
    with patch("src.main.run", side_effect=RuntimeError("no key")):
        code = _run_main()
    assert code == 2


def test_main_returns_2_on_file_not_found():
    """FileNotFoundError (missing input file) must return exit code 2."""
    with patch("src.main.run", side_effect=FileNotFoundError("r.tex not found")):
        code = _run_main()
    assert code == 2


# ---------------------------------------------------------------------------
# New: broad Exception handler (must return 1, not 2)
# ---------------------------------------------------------------------------

def test_main_returns_1_on_value_error(capsys):
    """ValueError (ledger drift / parse failure) must return exit code 1."""
    with patch("src.main.run", side_effect=ValueError("ledger drift")):
        code = _run_main()
    assert code == 1
    captured = capsys.readouterr()
    assert "unexpected failure" in captured.err


def test_main_returns_1_on_unexpected_exception():
    """Any other Exception must return exit code 1 (not crash raw)."""
    with patch("src.main.run", side_effect=Exception("boom")):
        code = _run_main()
    assert code == 1


def test_run_seeds_jd_name_from_jd_path(tmp_path):
    """run() must seed jd_name as the stem of the jd file path."""
    resume = tmp_path / "resume.tex"
    jd = tmp_path / "amazon_sde.txt"
    resume.write_text(r"\documentclass{article}\begin{document}\end{document}")
    jd.write_text("Software Development Engineer II")

    captured_state: dict = {}

    def fake_graph_stream(state, config, stream_mode):
        captured_state.update(state)
        return iter([])

    import src.main as main_mod
    from unittest.mock import MagicMock
    fake_graph = MagicMock()
    fake_graph.stream = fake_graph_stream

    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=fake_graph):
        main_mod.run(str(resume), str(jd), str(tmp_path / "out"))

    assert captured_state.get("jd_name") == "amazon_sde"


def test_main_returns_1_on_graph_recursion_error(capsys):
    """GraphRecursionError must return exit code 1 with a recursion message."""
    try:
        from langgraph.errors import GraphRecursionError
        exc = GraphRecursionError("recursion limit exceeded")
    except ImportError:
        pytest.skip("langgraph not installed — skipping GraphRecursionError test")

    with patch("src.main.run", side_effect=exc):
        code = _run_main()

    assert code == 1
    captured = capsys.readouterr()
    assert "recursion" in captured.err.lower()
