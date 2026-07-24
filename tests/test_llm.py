"""Tests for src.pipeline.llm — importability, callables, and model_context."""
import importlib
import types

from pydantic import BaseModel


class _DummySchema(BaseModel):
    """Placeholder schema — _parse is mocked in these tests, so its shape never matters."""


def _fake_openai_client(captured: dict, parsed: object = "PARSED"):
    """Build a stand-in for llm.client() that records completions.parse(**kwargs)."""

    def fake_completions_parse(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            usage=None,
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(parsed=parsed))],
        )

    return types.SimpleNamespace(
        beta=types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(parse=fake_completions_parse)
            )
        )
    )


def test_llm_imports_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import src.pipeline.llm as llm

    importlib.reload(llm)
    assert llm is not None


def test_helpers_are_callable():
    import src.pipeline.llm as llm

    assert callable(llm.client)
    assert callable(llm.parse_fast)
    assert callable(llm.parse_strong)
    assert callable(llm.model_context)


def test_client_is_cached():
    """client() must be lru_cache-wrapped (lazy singleton)."""
    import src.pipeline.llm as llm

    assert hasattr(llm.client, "cache_clear")


def test_model_context_injects_and_resets():
    """model_context must override context vars for its block then restore them."""
    from src.pipeline.llm import _ctx_model_fast, _ctx_model_strong, model_context

    with model_context(fast="fast-test", strong="strong-test"):
        assert _ctx_model_fast.get() == "fast-test"
        assert _ctx_model_strong.get() == "strong-test"

    # Vars restored to default (None) after exiting.
    assert _ctx_model_fast.get() is None
    assert _ctx_model_strong.get() is None


def test_model_context_yields_usage_list():
    """model_context yields a mutable list that accumulates usage records."""
    from src.pipeline.llm import model_context

    with model_context(fast="f", strong="s") as usage:
        assert isinstance(usage, list)
        usage.append({"model": "f", "input_tokens": 10, "output_tokens": 5})

    assert len(usage) == 1


def test_model_context_resets_on_exception():
    """Context vars are reset even when the body raises."""
    from src.pipeline.llm import _ctx_model_fast, model_context

    try:
        with model_context(fast="boom-fast", strong="boom-strong"):
            raise RuntimeError("intentional")
    except RuntimeError:
        pass

    assert _ctx_model_fast.get() is None


# --- per-tier max_tokens ceilings ----------------------------------------------
#
# DEFAULT_MAX_TOKENS (16000) is sized just under gpt-4o-mini's real 16,384-token
# output ceiling (MODEL_FAST / MODEL_SCORING). MODEL_STRONG / MODEL_GAP are
# Anthropic reasoning models whose extended-thinking tokens bill against that
# SAME completion budget — 16000 is too tight for them and previously caused
# openai.LengthFinishReasonError on real writer runs (reasoning ate the ceiling
# before the structured output could be emitted). These calls need a distinct,
# higher default; the gpt-4o-mini calls must NOT get pushed past their real cap.


def test_default_max_tokens_stays_under_gpt4o_mini_output_ceiling():
    import src.pipeline.llm as llm

    assert llm.DEFAULT_MAX_TOKENS <= 16384


def test_reasoning_max_tokens_is_meaningfully_larger_than_default():
    import src.pipeline.llm as llm

    assert llm.REASONING_MAX_TOKENS > llm.DEFAULT_MAX_TOKENS


def test_parse_strong_defaults_to_reasoning_max_tokens(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    out = llm.parse_strong("sys", "user", _DummySchema)

    assert out == "PARSED"
    assert captured["max_tokens"] == llm.REASONING_MAX_TOKENS


def test_parse_gap_defaults_to_reasoning_max_tokens(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    out = llm.parse_gap("sys", "user", _DummySchema)

    assert out == "PARSED"
    assert captured["max_tokens"] == llm.REASONING_MAX_TOKENS


def test_parse_fast_keeps_default_max_tokens(monkeypatch):
    """The gpt-4o-mini-backed calls must NOT be bumped past their real ceiling."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_fast("sys", "user", _DummySchema)

    assert captured["max_tokens"] == llm.DEFAULT_MAX_TOKENS


def test_parse_scoring_keeps_default_max_tokens(monkeypatch):
    """The gpt-4o-mini-backed calls must NOT be bumped past their real ceiling."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_scoring("sys", "user", _DummySchema)

    assert captured["max_tokens"] == llm.DEFAULT_MAX_TOKENS


def test_parse_strong_caller_can_still_override_max_tokens(monkeypatch):
    """An explicit max_tokens kwarg must still win over the reasoning default."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_strong("sys", "user", _DummySchema, max_tokens=9999)

    assert captured["max_tokens"] == 9999


# --- per-tier reasoning effort --------------------------------------------------
#
# EFFORT_STRONG / EFFORT_GAP live in config.settings so reasoning depth can be
# retuned in one place. parse_strong / parse_gap must default to those settings
# and forward the value all the way to _parse(); parse_fast / parse_scoring
# (gpt-4o-mini, not a reasoning model) must never forward an effort at all.


def test_parse_strong_defaults_to_configured_effort(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_strong("sys", "user", _DummySchema)

    assert captured["effort"] == llm.EFFORT_STRONG


def test_parse_gap_defaults_to_configured_effort(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_gap("sys", "user", _DummySchema)

    assert captured["effort"] == llm.EFFORT_GAP


def test_parse_strong_caller_can_still_override_effort(monkeypatch):
    """An explicit effort kwarg must still win over the settings-driven default."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_strong("sys", "user", _DummySchema, effort="low")

    assert captured["effort"] == "low"


def test_parse_gap_caller_can_still_override_effort(monkeypatch):
    """An explicit effort kwarg must still win over the settings-driven default."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_gap("sys", "user", _DummySchema, effort="max")

    assert captured["effort"] == "max"


def test_parse_fast_never_forwards_an_effort(monkeypatch):
    """gpt-4o-mini isn't a reasoning model — parse_fast must not set an effort."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_fast("sys", "user", _DummySchema)

    assert captured["effort"] is None


def test_parse_scoring_never_forwards_an_effort(monkeypatch):
    """gpt-4o-mini isn't a reasoning model — parse_scoring must not set an effort."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_scoring("sys", "user", _DummySchema)

    assert captured["effort"] is None


# --- parse_skills (one-shot skill dump on MODEL_SKILLS) ------------------------
#
# parse_skills targets gpt-4o-mini (MODEL_SKILLS). gpt-4o-mini is NOT a
# reasoning model and rejects the reasoning effort field, so parse_skills
# must NOT forward any effort by default (same invariant as parse_fast /
# parse_scoring). Its max_tokens default is DEFAULT_MAX_TOKENS (not
# REASONING_MAX_TOKENS) since gpt-4o-mini caps at ~16k.


def test_parse_skills_does_not_forward_effort_by_default(monkeypatch):
    """gpt-4o-mini isn't a reasoning model — parse_skills must not set an effort."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema)

    assert captured["effort"] is None


def test_parse_skills_defaults_to_default_max_tokens(monkeypatch):
    """gpt-4o-mini-backed — must use DEFAULT_MAX_TOKENS, NOT the reasoning ceiling."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["max_tokens"] = max_tokens
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema)

    assert captured["max_tokens"] == llm.DEFAULT_MAX_TOKENS


def test_parse_skills_caller_can_override_effort(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema, effort="high")

    assert captured["effort"] == "high"


def test_parse_skills_defaults_to_model_skills(monkeypatch):
    """With no override in context, parse_skills resolves to MODEL_SKILLS."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["model"] = model
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema)

    assert captured["model"] == llm.MODEL_SKILLS


def test_model_context_sets_and_resets_skills_var():
    """model_context(skills=...) overrides _ctx_model_skills then restores it."""
    from src.pipeline.llm import _ctx_model_skills, model_context

    with model_context(fast="f", strong="s", skills="skills-override"):
        assert _ctx_model_skills.get() == "skills-override"

    assert _ctx_model_skills.get() is None


def test_model_context_skills_override_wins_in_parse_skills(monkeypatch):
    """A skills= override on model_context takes precedence over MODEL_SKILLS."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["model"] = model
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", skills="anthropic/claude-opus-5"):
        llm.parse_skills("sys", "user", _DummySchema)

    assert captured["model"] == "anthropic/claude-opus-5"


def test_parse_forwards_effort_via_openrouter_reasoning_extra_body(monkeypatch):
    """_parse must translate effort into OpenRouter's unified reasoning field —
    it is not a native OpenAI SDK kwarg, so it has to ride in extra_body."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    out = llm._parse("sys", "user", _DummySchema, "some/model", 1234, effort="high")

    assert out == "PARSED"
    assert captured["extra_body"] == {"reasoning": {"effort": "high"}}


def test_parse_omits_extra_body_when_effort_is_none(monkeypatch):
    """Non-reasoning calls (parse_fast / parse_scoring) must not send a reasoning
    field at all — gpt-4o-mini has no effort knob."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234)

    assert "extra_body" not in captured
