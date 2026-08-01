"""Tests for src.pipeline.llm - importability, callables, and model_context."""
import importlib
import types

from pydantic import BaseModel


class _DummySchema(BaseModel):
    """Placeholder schema - _parse is mocked in these tests, so its shape never matters."""


def _fake_openai_client(captured: dict):
    """Build a stand-in for llm.client() that records chat.completions.create(**kwargs)."""

    def fake_completions_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            usage=None,
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=fake_completions_create)
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
# SAME completion budget - 16000 is too tight for them and previously caused
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
    """gpt-4o-mini isn't a reasoning model - parse_fast must not set an effort."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_fast("sys", "user", _DummySchema)

    assert captured["effort"] is None


def test_parse_scoring_never_forwards_an_effort(monkeypatch):
    """gpt-4o-mini isn't a reasoning model - parse_scoring must not set an effort."""
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
    """gpt-4o-mini isn't a reasoning model - parse_skills must not set an effort."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema)

    assert captured["effort"] is None


def test_parse_skills_defaults_to_default_max_tokens(monkeypatch):
    """gpt-4o-mini-backed - must use DEFAULT_MAX_TOKENS, NOT the reasoning ceiling."""
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
    """_parse must translate effort into OpenRouter's unified reasoning field -
    it is not a native OpenAI SDK kwarg, so it has to ride in extra_body."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234, effort="high")

    assert captured["extra_body"] == {"reasoning": {"effort": "high"}}


def test_parse_forwards_effort_none_string_to_disable_reasoning(monkeypatch):
    """effort='none' is OpenRouter's disable flag — must be sent, not omitted.

    Distinct from Python None, which omits the reasoning block entirely
    (for non-reasoning models that reject the parameter).
    """
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234, effort="none")

    assert captured.get("extra_body") == {"reasoning": {"effort": "none"}}


def test_parse_omits_extra_body_when_effort_is_none(monkeypatch):
    """Non-reasoning calls (parse_fast / parse_scoring) must not send a reasoning
    field at all - gpt-4o-mini has no effort knob."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234)

    assert "extra_body" not in captured


# --- tool-call fallback when message.content is empty --------------------------
#
# Some providers (Anthropic via OpenRouter, under extended thinking) emit
# strict-json_schema output as a forced tool call instead of populating
# message.content - the thinking block consumes the only text turn. _parse
# must fall back to the first tool call's arguments before treating the
# response as genuinely empty (which previously surfaced as "Empty response
# content for WriterOutput - model returned nothing" on real writer runs).


def _fake_client_with_tool_call(arguments: str, content: object = None):
    """Stand-in whose response has empty message.content but a populated tool call."""

    def fake_completions_create(**kwargs):
        return types.SimpleNamespace(
            usage=None,
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content=content,
                        tool_calls=[
                            types.SimpleNamespace(
                                function=types.SimpleNamespace(arguments=arguments)
                            )
                        ],
                    )
                )
            ],
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=fake_completions_create)
        )
    )


def test_parse_falls_back_to_tool_call_arguments_when_content_empty(monkeypatch):
    import src.pipeline.llm as llm

    monkeypatch.setattr(
        llm, "client", lambda: _fake_client_with_tool_call(arguments="{}")
    )

    out = llm._parse("sys", "user", _DummySchema, "some/model", 1234)

    assert isinstance(out, _DummySchema)


def test_parse_raises_when_content_and_tool_calls_both_empty(monkeypatch):
    import pytest

    import src.pipeline.llm as llm

    def fake_completions_create(**kwargs):
        return types.SimpleNamespace(
            usage=None,
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=None, tool_calls=None)
                )
            ],
        )

    monkeypatch.setattr(
        llm,
        "client",
        lambda: types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=fake_completions_create)
            )
        ),
    )

    with pytest.raises(ValueError, match="Empty response content"):
        llm._parse("sys", "user", _DummySchema, "some/model", 1234)


def test_runner_forwards_effort_none_through_model_context():
    """When a role's effort is the string 'none', model_context must surface it."""
    from src.pipeline.llm import _ctx_effort_strong, model_context

    with model_context(fast="f", strong="s", effort_strong="none"):
        assert _ctx_effort_strong.get() == "none"


# --- per-run effort overrides via model_context ---------------------------------


def test_model_context_effort_overrides_parse_strong_default(monkeypatch):
    """model_context(effort_strong=...) wins over EFFORT_STRONG for parse_strong."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", effort_strong="max"):
        llm.parse_strong("sys", "user", _DummySchema)

    assert captured["effort"] == "max"


def test_model_context_effort_none_suppresses_parse_strong_reasoning(monkeypatch):
    """Explicit None effort in context means no reasoning param (non-reasoning writer)."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        captured["called_with_effort_kw"] = True
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", effort_strong=None):
        llm.parse_strong("sys", "user", _DummySchema)

    assert captured["effort"] is None


def test_model_context_effort_fast_forwards_from_parse_fast(monkeypatch):
    """When context sets effort_fast, parse_fast forwards it."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", effort_fast="low"):
        llm.parse_fast("sys", "user", _DummySchema)

    assert captured["effort"] == "low"


def test_model_context_effort_scoring_forwards_from_parse_scoring(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", effort_scoring="high"):
        llm.parse_scoring("sys", "user", _DummySchema)

    assert captured["effort"] == "high"


def test_model_context_effort_skills_forwards_from_parse_skills(monkeypatch):
    """model_context(effort_skills=...) is picked up by parse_skills."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, effort=None):
        captured["effort"] = effort
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", effort_skills="medium"):
        llm.parse_skills("sys", "user", _DummySchema)

    assert captured["effort"] == "medium"


def test_model_context_resets_effort_vars():
    from src.pipeline.llm import _UNSET, _ctx_effort_skills, _ctx_effort_strong, model_context

    with model_context(fast="f", strong="s", effort_strong="high", effort_skills="low"):
        assert _ctx_effort_strong.get() == "high"
        assert _ctx_effort_skills.get() == "low"

    assert _ctx_effort_strong.get() is _UNSET
    assert _ctx_effort_skills.get() is _UNSET


# --- per-tier temperature -----------------------------------------------------
#
# temperature is a native OpenAI/OpenRouter chat-completions parameter (unlike
# `effort`, which OpenRouter only accepts via extra_body). No role has a
# config.settings default - it stays None (omitted, provider default) unless a
# caller passes an explicit value or model_context sets a temp_* override.
# 0 is a legitimate override and must never be treated as falsy/unset.


def test_parse_forwards_temperature_as_native_kwarg(monkeypatch):
    """_parse must pass temperature straight through - no extra_body wrapping."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234, temperature=0.7)

    assert captured["temperature"] == 0.7
    assert "extra_body" not in captured


def test_parse_omits_temperature_when_none(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234)

    assert "temperature" not in captured


def test_parse_forwards_temperature_zero_not_treated_as_falsy(monkeypatch):
    """0 is a legitimate temperature override - must not be dropped like None."""
    import src.pipeline.llm as llm

    captured = {}
    monkeypatch.setattr(llm, "client", lambda: _fake_openai_client(captured))

    llm._parse("sys", "user", _DummySchema, "some/model", 1234, temperature=0.0)

    assert captured["temperature"] == 0.0


def test_model_context_sets_and_resets_temperature_vars():
    from src.pipeline.llm import (
        _UNSET,
        _ctx_temp_fast,
        _ctx_temp_gap,
        _ctx_temp_scoring,
        _ctx_temp_skills,
        _ctx_temp_strong,
        model_context,
    )

    with model_context(
        fast="f",
        strong="s",
        temp_fast=0.0,
        temp_strong=0.7,
        temp_gap=0.5,
        temp_scoring=0.2,
        temp_skills=0.2,
    ):
        assert _ctx_temp_fast.get() == 0.0
        assert _ctx_temp_strong.get() == 0.7
        assert _ctx_temp_gap.get() == 0.5
        assert _ctx_temp_scoring.get() == 0.2
        assert _ctx_temp_skills.get() == 0.2

    assert _ctx_temp_fast.get() is _UNSET
    assert _ctx_temp_strong.get() is _UNSET
    assert _ctx_temp_gap.get() is _UNSET
    assert _ctx_temp_scoring.get() is _UNSET
    assert _ctx_temp_skills.get() is _UNSET


def test_parse_strong_omits_temperature_by_default(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_strong("sys", "user", _DummySchema)

    assert "temperature" not in captured


def test_parse_strong_forwards_explicit_temperature_kwarg(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_strong("sys", "user", _DummySchema, temperature=0.7)

    assert captured["temperature"] == 0.7


def test_parse_strong_forwards_temperature_from_context_override(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_strong=0.9):
        llm.parse_strong("sys", "user", _DummySchema)

    assert captured["temperature"] == 0.9


def test_parse_strong_explicit_temperature_wins_over_context(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_strong=0.9):
        llm.parse_strong("sys", "user", _DummySchema, temperature=0.1)

    assert captured["temperature"] == 0.1


def test_parse_fast_forwards_temperature_zero_from_context(monkeypatch):
    """0 is a legitimate override for parse_fast - must not be dropped as falsy."""
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_fast=0.0):
        llm.parse_fast("sys", "user", _DummySchema)

    assert captured["temperature"] == 0.0


def test_parse_gap_forwards_temperature_from_context(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_gap=0.5):
        llm.parse_gap("sys", "user", _DummySchema)

    assert captured["temperature"] == 0.5


def test_parse_scoring_forwards_temperature_from_context(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_scoring=0.2):
        llm.parse_scoring("sys", "user", _DummySchema)

    assert captured["temperature"] == 0.2


def test_parse_skills_forwards_temperature_from_context(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    with llm.model_context(fast="f", strong="s", temp_skills=0.2):
        llm.parse_skills("sys", "user", _DummySchema)

    assert captured["temperature"] == 0.2


def test_parse_skills_forwards_explicit_temperature_kwarg(monkeypatch):
    import src.pipeline.llm as llm

    captured = {}

    def fake_parse(system, user, schema, model, max_tokens, **kwargs):
        captured.update(kwargs)
        return "PARSED"

    monkeypatch.setattr(llm, "_parse", fake_parse)

    llm.parse_skills("sys", "user", _DummySchema, temperature=0.3)

    assert captured["temperature"] == 0.3


# --- effective_* introspection (for accurate "sending to X" logging) -----------
#
# Agent node files log "sending to <model> (effort=..., temp=...)" BEFORE
# calling parse_*. That line must reflect what parse_* will ACTUALLY use for
# THIS run - not the static config.settings constants - or the log lies
# whenever a per-job model_context override is active. effective_* returns
# the same (model, effort, temperature) resolution parse_* itself would use.


def test_effective_fast_defaults_to_settings_model_and_no_effort_or_temp():
    import src.pipeline.llm as llm

    role = llm.effective_fast()

    assert role.model == llm.MODEL_FAST
    assert role.effort is None
    assert role.temperature is None


def test_effective_fast_reflects_context_overrides():
    import src.pipeline.llm as llm

    with llm.model_context(fast="f", strong="s", effort_fast="low", temp_fast=0.3):
        role = llm.effective_fast()

    assert role.model == "f"
    assert role.effort == "low"
    assert role.temperature == 0.3


def test_effective_strong_defaults_to_settings_model_and_effort():
    import src.pipeline.llm as llm

    role = llm.effective_strong()

    assert role.model == llm.MODEL_STRONG
    assert role.effort == llm.EFFORT_STRONG
    assert role.temperature is None


def test_effective_strong_reflects_context_overrides():
    import src.pipeline.llm as llm

    with llm.model_context(
        fast="f", strong="s", effort_strong="max", temp_strong=0.7
    ):
        role = llm.effective_strong()

    assert role.model == "s"
    assert role.effort == "max"
    assert role.temperature == 0.7


def test_effective_gap_defaults_to_settings_model_and_effort():
    import src.pipeline.llm as llm

    role = llm.effective_gap()

    assert role.model == llm.MODEL_GAP
    assert role.effort == llm.EFFORT_GAP
    assert role.temperature is None


def test_effective_gap_reflects_context_overrides():
    import src.pipeline.llm as llm

    with llm.model_context(
        fast="f", strong="s", gap="z-ai/glm-5.2", effort_gap="high", temp_gap=0.5
    ):
        role = llm.effective_gap()

    assert role.model == "z-ai/glm-5.2"
    assert role.effort == "high"
    assert role.temperature == 0.5


def test_effective_scoring_defaults_to_settings_model_and_no_effort():
    import src.pipeline.llm as llm

    role = llm.effective_scoring()

    assert role.model == llm.MODEL_SCORING
    assert role.effort is None
    assert role.temperature is None


def test_effective_scoring_reflects_context_overrides():
    import src.pipeline.llm as llm

    with llm.model_context(
        fast="f",
        strong="s",
        scoring="deepseek/deepseek-v4-flash",
        effort_scoring="xhigh",
        temp_scoring=0.2,
    ):
        role = llm.effective_scoring()

    assert role.model == "deepseek/deepseek-v4-flash"
    assert role.effort == "xhigh"
    assert role.temperature == 0.2


def test_effective_skills_defaults_to_settings_model_and_no_effort():
    import src.pipeline.llm as llm

    role = llm.effective_skills()

    assert role.model == llm.MODEL_SKILLS
    assert role.effort is None
    assert role.temperature is None


def test_effective_skills_reflects_context_overrides():
    import src.pipeline.llm as llm

    with llm.model_context(
        fast="f",
        strong="s",
        skills="qwen/qwen3-30b-a3b-instruct-2507",
        effort_skills="medium",
        temp_skills=0.2,
    ):
        role = llm.effective_skills()

    assert role.model == "qwen/qwen3-30b-a3b-instruct-2507"
    assert role.effort == "medium"
    assert role.temperature == 0.2
