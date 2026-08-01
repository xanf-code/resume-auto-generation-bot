"""Phase 7 - tests for src.main.stream_pipeline.

stream_pipeline is the content-based, callback-driven core extracted from run().
It accepts raw resume/JD strings (no file paths), calls require_api_key() before
building the graph, invokes on_step(flat_delta, accumulated_state) once per
streamed node, prints nothing, and returns the accumulated final_state.
"""
from unittest.mock import MagicMock, patch

import pytest


_SCRIPT = [
    {"parse_resume": {"identity_ledger": "L", "resume_struct": "S"}},
    {"analyze_jd": {"jd_vector": "V"}},
    {"aggregator": {"aggregate_score": 80.0, "passed": True}},
]


def _fake_stream(state, config, stream_mode):
    assert stream_mode == "updates"
    return iter(_SCRIPT)


def test_stream_pipeline_calls_require_api_key_before_building_graph():
    order: list[str] = []

    def rec_require():
        order.append("require")
        return "key"

    def rec_build(enable_scoring=False):
        order.append("build")
        g = MagicMock()
        g.stream = _fake_stream
        return g

    from src.main import stream_pipeline
    with patch("src.main.require_api_key", side_effect=rec_require), \
         patch("src.main.build_graph", side_effect=rec_build):
        stream_pipeline("resume tex", "jd text", out_dir="out", jd_name="acme")

    assert order == ["require", "build"]


def test_stream_pipeline_invokes_on_step_per_node_with_accumulated_state():
    seen: list[tuple[dict, dict]] = []

    def on_step(flat, state):
        seen.append((dict(flat), dict(state)))

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = _fake_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme", on_step=on_step)

    # one call per streamed node
    assert len(seen) == 3
    # accumulation: later states contain earlier keys
    assert "identity_ledger" in seen[0][1] and "jd_vector" not in seen[0][1]
    assert "jd_vector" in seen[1][1]
    assert seen[2][1]["aggregate_score"] == 80.0
    assert seen[2][1]["passed"] is True


def test_stream_pipeline_returns_accumulated_final_state():
    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = _fake_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        final = stream_pipeline("r", "j", out_dir="out", jd_name="acme")

    assert final["identity_ledger"] == "L"
    assert final["jd_vector"] == "V"
    assert final["aggregate_score"] == 80.0
    assert final["passed"] is True


def test_stream_pipeline_seeds_initial_state_fields():
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("R", "J", out_dir="out/x", jd_name="acme", enable_scoring=True)

    assert captured["resume_tex_raw"] == "R"
    assert captured["jd_raw"] == "J"
    assert captured["out_dir"] == "out/x"
    assert captured["jd_name"] == "acme"
    assert captured["enable_scoring"] is True
    assert captured["iteration"] == 1


def test_stream_pipeline_seeds_default_tuning_when_absent():
    from src.pipeline.tuning import PipelineTuning

    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        captured["_config"] = config
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("R", "J", out_dir="out/x", jd_name="acme")

    assert captured["tuning"] == PipelineTuning.defaults()
    # recursion limit scales off the (default) max_iterations
    assert captured["_config"]["recursion_limit"] == PipelineTuning.defaults().max_iterations * 12 + 20


def test_stream_pipeline_seeds_supplied_tuning_and_scales_recursion():
    import dataclasses

    from src.pipeline.tuning import PipelineTuning

    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        captured["_config"] = config
        return iter([])

    roomy = dataclasses.replace(PipelineTuning.defaults(), max_iterations=8)

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("R", "J", out_dir="out/x", jd_name="acme", tuning=roomy)

    assert captured["tuning"] is roomy
    assert captured["_config"]["recursion_limit"] == 8 * 12 + 20


def test_stream_pipeline_does_no_file_io_and_no_stdout(capsys):
    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = _fake_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g), \
         patch("src.main._read_text", side_effect=AssertionError("must not read files")):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme")

    out = capsys.readouterr().out
    assert "Running resume-bot pipeline" not in out
    assert "=" * 52 not in out


def test_stream_pipeline_seeds_proven_examples_when_set():
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme",
                        proven_examples="## PROVEN EXAMPLES\n- did a thing")

    assert captured["proven_examples"] == "## PROVEN EXAMPLES\n- did a thing"


def test_stream_pipeline_omits_proven_examples_key_when_none():
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme")

    assert "proven_examples" not in captured


def test_stream_pipeline_seeds_jd_domains_when_set():
    """The web path pre-computes the JD role/domain classification once
    (inside its own model_context, so it honors the job's Parser config) and
    hands the result down here - analyze_jd's node reuses it instead of
    calling classify_jd_type a second, independent time."""
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme",
                        jd_domains=["fintech", "ai"])

    assert captured["jd_domains"] == ["fintech", "ai"]


def test_stream_pipeline_omits_jd_domains_key_when_none():
    """CLI callers that don't pre-classify must not seed the key at all -
    analyze_jd's ``state.get("jd_domains")`` check needs it truly absent (not
    an empty list) to know it should compute the classification itself."""
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme")

    assert "jd_domains" not in captured


def test_stream_pipeline_seeds_jd_domains_empty_list_when_explicitly_set():
    """An explicit empty list (JD tagged no domains) must still be seeded -
    distinct from None/omitted, mirroring the None-vs-0 distinction used
    elsewhere in this codebase for "unset" vs "meaningfully empty"."""
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme", jd_domains=[])

    assert captured["jd_domains"] == []


def test_stream_pipeline_forwards_cached_struct_and_ledger():
    captured: dict = {}

    def capture_stream(state, config, stream_mode):
        captured.update(state)
        return iter([])

    from src.main import stream_pipeline
    g = MagicMock()
    g.stream = capture_stream
    struct, ledger = object(), object()
    with patch("src.main.require_api_key", return_value="key"), \
         patch("src.main.build_graph", return_value=g):
        stream_pipeline("r", "j", out_dir="out", jd_name="acme",
                        resume_struct=struct, identity_ledger=ledger)

    assert captured["resume_struct"] is struct
    assert captured["identity_ledger"] is ledger
