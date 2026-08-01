"""OpenRouter client helpers for structured-output parsing.

Uses the OpenAI-compatible API at https://openrouter.ai/api/v1.
Importable with no API key present - the client is instantiated lazily and
cached, so ``require_api_key`` only fires on the first real call.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Any, Generator, TypeVar

import openai
from pydantic import BaseModel

from config.settings import (
    EFFORT_GAP,
    EFFORT_STRONG,
    MODEL_FAST,
    MODEL_GAP,
    MODEL_SCORING,
    MODEL_SKILLS,
    MODEL_STRONG,
    require_api_key,
)
from src.pipeline.models import ModelRole

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Sized just under gpt-4o-mini's real 16,384-token output ceiling
# (MODEL_FAST / MODEL_SCORING) - do not raise this without checking that cap.
DEFAULT_MAX_TOKENS = 16_000
# MODEL_STRONG / MODEL_GAP are Anthropic reasoning models whose extended-
# thinking tokens bill against the SAME completion budget as the structured
# output. DEFAULT_MAX_TOKENS is too tight for them - reasoning alone can eat
# the ceiling before the schema is emitted, surfacing as
# openai.LengthFinishReasonError. These two calls get more headroom.
REASONING_MAX_TOKENS = 32_000

# Sentinel: ContextVar / kwarg default meaning "use role settings default".
_UNSET: Any = object()

# Per-run model overrides - set by model_context(); default to None (→ config constants).
_ctx_model_fast: ContextVar[str | None] = ContextVar("model_fast", default=None)
_ctx_model_strong: ContextVar[str | None] = ContextVar("model_strong", default=None)
_ctx_model_gap: ContextVar[str | None] = ContextVar("model_gap", default=None)
_ctx_model_scoring: ContextVar[str | None] = ContextVar("model_scoring", default=None)
_ctx_model_skills: ContextVar[str | None] = ContextVar("model_skills", default=None)

# Per-run effort overrides. Default _UNSET → use EFFORT_* / no effort for fast roles.
# Explicit None in context means "do not send reasoning" (non-reasoning model).
_ctx_effort_fast: ContextVar[Any] = ContextVar("effort_fast", default=_UNSET)
_ctx_effort_strong: ContextVar[Any] = ContextVar("effort_strong", default=_UNSET)
_ctx_effort_gap: ContextVar[Any] = ContextVar("effort_gap", default=_UNSET)
_ctx_effort_scoring: ContextVar[Any] = ContextVar("effort_scoring", default=_UNSET)
_ctx_effort_skills: ContextVar[Any] = ContextVar("effort_skills", default=_UNSET)

# Per-run temperature overrides. Default _UNSET → no config.settings default exists
# for any role (unlike effort); temperature is omitted (provider default) unless a
# caller passes an explicit value or model_context sets a temp_* override here.
_ctx_temp_fast: ContextVar[Any] = ContextVar("temp_fast", default=_UNSET)
_ctx_temp_strong: ContextVar[Any] = ContextVar("temp_strong", default=_UNSET)
_ctx_temp_gap: ContextVar[Any] = ContextVar("temp_gap", default=_UNSET)
_ctx_temp_scoring: ContextVar[Any] = ContextVar("temp_scoring", default=_UNSET)
_ctx_temp_skills: ContextVar[Any] = ContextVar("temp_skills", default=_UNSET)

# Accumulates raw usage dicts [{model, input_tokens, output_tokens}] when set.
_ctx_usage: ContextVar[list | None] = ContextVar("usage", default=None)


@contextmanager
def model_context(
    fast: str,
    strong: str,
    gap: str | None = None,
    scoring: str | None = None,
    skills: str | None = None,
    *,
    effort_fast: str | None | Any = _UNSET,
    effort_strong: str | None | Any = _UNSET,
    effort_gap: str | None | Any = _UNSET,
    effort_scoring: str | None | Any = _UNSET,
    effort_skills: str | None | Any = _UNSET,
    temp_fast: float | None | Any = _UNSET,
    temp_strong: float | None | Any = _UNSET,
    temp_gap: float | None | Any = _UNSET,
    temp_scoring: float | None | Any = _UNSET,
    temp_skills: float | None | Any = _UNSET,
) -> Generator[list[dict], None, None]:
    """Inject model (and optional effort/temperature) overrides for one pipeline run.

    Args:
        fast: Model for extraction (parser, JD analyzer).
        strong: Model for writer.
        gap: Model for gap analyzer (creative reframing strategy).
             Defaults to ``strong`` if not provided.
        scoring: Model for scoring panel (recruiters + aggregator).
                 Defaults to ``fast`` if not provided.
        skills: Model for the skill-dump node.
                Defaults to ``MODEL_SKILLS`` (config constant) if not provided.
        effort_*: Optional reasoning effort per role. Omit to keep role defaults;
            pass ``None`` to suppress the reasoning parameter entirely.
        temp_*: Optional sampling temperature per role. Omit to keep role
            defaults (no config.settings default exists for any role - the
            parameter is omitted entirely, letting the provider pick); pass an
            explicit float (including ``0``) to override.

    Usage::

        with model_context(fast="openai/gpt-4o-mini",
                           strong="anthropic/claude-opus-5",
                           gap="anthropic/claude-opus-5",
                           scoring="openai/gpt-4o-mini",
                           skills="openai/gpt-4o-mini",
                           effort_strong="high",
                           temp_strong=0.7) as usage:
            run_pipeline(...)
        cost = compute_cost(usage)
    """
    t_fast = _ctx_model_fast.set(fast)
    t_strong = _ctx_model_strong.set(strong)
    t_gap = _ctx_model_gap.set(gap or strong)
    t_scoring = _ctx_model_scoring.set(scoring or fast)
    t_skills = _ctx_model_skills.set(skills)
    t_ef = _ctx_effort_fast.set(effort_fast)
    t_es = _ctx_effort_strong.set(effort_strong)
    t_eg = _ctx_effort_gap.set(effort_gap)
    t_esc = _ctx_effort_scoring.set(effort_scoring)
    t_esk = _ctx_effort_skills.set(effort_skills)
    t_tf = _ctx_temp_fast.set(temp_fast)
    t_ts = _ctx_temp_strong.set(temp_strong)
    t_tg = _ctx_temp_gap.set(temp_gap)
    t_tsc = _ctx_temp_scoring.set(temp_scoring)
    t_tsk = _ctx_temp_skills.set(temp_skills)
    usage: list[dict] = []
    t_usage = _ctx_usage.set(usage)
    try:
        yield usage
    finally:
        _ctx_model_fast.reset(t_fast)
        _ctx_model_strong.reset(t_strong)
        _ctx_model_gap.reset(t_gap)
        _ctx_model_scoring.reset(t_scoring)
        _ctx_model_skills.reset(t_skills)
        _ctx_effort_fast.reset(t_ef)
        _ctx_effort_strong.reset(t_es)
        _ctx_effort_gap.reset(t_eg)
        _ctx_effort_scoring.reset(t_esc)
        _ctx_effort_skills.reset(t_esk)
        _ctx_temp_fast.reset(t_tf)
        _ctx_temp_strong.reset(t_ts)
        _ctx_temp_gap.reset(t_tg)
        _ctx_temp_scoring.reset(t_tsc)
        _ctx_temp_skills.reset(t_tsk)
        _ctx_usage.reset(t_usage)


@lru_cache(maxsize=1)
def client() -> openai.OpenAI:
    """Return a cached OpenRouter client (validates the API key on first call)."""
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=require_api_key(),
    )


def _system_message(model: str, system: str) -> dict:
    """Build the system message dict for the given model.

    Anthropic models support prompt caching via cache_control on content blocks.
    Caching the system prompt saves ~90% of its input-token cost on every call
    after the first within the 5-minute cache window — meaningful because the
    writer and gap system prompts are large (10-19 KB) and fire repeatedly.
    Non-Anthropic models (gpt-4o-mini) receive the plain string form.
    """
    if model.startswith("anthropic/"):
        return {
            "role": "system",
            "content": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        }
    return {"role": "system", "content": system}


def _parse(
    system: str,
    user: str,
    schema: type[SchemaT],
    model: str,
    max_tokens: int,
    effort: str | None = None,
    temperature: float | None = None,
) -> SchemaT:
    extra_body: dict = {}
    if effort is not None:
        # OpenRouter's unified reasoning parameter. Anthropic models translate
        # this into a thinking-effort depth; the thinking token budget is
        # calculated from max_tokens. effort="none" is intentional: send it so
        # OpenRouter disables reasoning. Python None (omit this block) is for
        # non-reasoning models.
        extra_body["reasoning"] = {"effort": effort}
    extra_kwargs: dict = {"extra_body": extra_body} if extra_body else {}
    if temperature is not None:
        extra_kwargs["temperature"] = temperature
    # Use chat.completions.create() with an explicit json_schema response_format
    # instead of beta.chat.completions.parse(). OpenRouter honors the json_schema
    # type natively across all providers; beta.parse() is an OpenAI-SDK abstraction
    # that OpenRouter doesn't fully implement for non-OpenAI models — Anthropic
    # thinking blocks can bleed into the response payload and cause JSONDecodeError.
    response = client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            _system_message(model, system),
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        },
        **extra_kwargs,
    )
    usage_log = _ctx_usage.get()
    if usage_log is not None and response.usage:
        usage_log.append({
            "model": model,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        })
    message = response.choices[0].message
    content = message.content
    if not content:
        # Some providers (notably Anthropic via OpenRouter, under extended
        # thinking) emit strict-json_schema output as a forced tool call
        # instead of populating message.content - the thinking block consumes
        # the only text turn, leaving content empty even though the model did
        # produce the structured payload. Fall back to the tool-call arguments
        # before treating the response as genuinely empty.
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            content = tool_calls[0].function.arguments
    if not content:
        raise ValueError(
            f"Empty response content for {schema.__name__} — model returned nothing."
        )
    parsed = schema.model_validate_json(content)
    return parsed


def _resolve_effort(explicit: Any, ctx_var: ContextVar[Any], default: str | None) -> str | None:
    """Resolve effort: explicit kwarg > context override > role default."""
    if explicit is not _UNSET:
        return explicit  # type: ignore[return-value]
    ctx = ctx_var.get()
    if ctx is not _UNSET:
        return ctx  # may be None (suppress reasoning)
    return default


def _resolve_temperature(
    explicit: Any, ctx_var: ContextVar[Any], default: float | None
) -> float | None:
    """Resolve temperature: explicit kwarg > context override > role default.

    Mirrors ``_resolve_effort``'s precedence. No role currently has a
    non-None ``default`` (temperature isn't a config.settings constant), but
    the signature stays symmetric with ``_resolve_effort`` for consistency.
    """
    if explicit is not _UNSET:
        return explicit  # type: ignore[return-value]
    ctx = ctx_var.get()
    if ctx is not _UNSET:
        return ctx  # may be None or 0 - both are meaningful, not "unset"
    return default


def _optional_kwargs(effort: str | None, temperature: float | None) -> dict[str, Any]:
    """Build the effort/temperature kwargs for `_parse`, omitting unset (None) values.

    Centralizes the "only forward what's actually set" rule so every parse_*
    role resolves the same way, whether the role has a reasoning default or not.
    """
    kwargs: dict[str, Any] = {}
    if effort is not None:
        kwargs["effort"] = effort
    if temperature is not None:
        kwargs["temperature"] = temperature
    return kwargs


# --- effective_* introspection --------------------------------------------------
#
# Agent node files log "sending to <model> (effort=..., temp=...)" before calling
# parse_*. That line must reflect what THIS run will actually send - not the
# static config.settings constants - or it lies whenever a model_context
# override is active (see the writer/gap "no override taken" bug this fixed).
# Each effective_* mirrors its parse_*'s own resolution exactly, with no
# explicit per-call override (matching how every current call site invokes
# parse_* - system/user/schema only, no explicit effort/temperature kwarg).


def effective_fast() -> ModelRole:
    """The (model, effort, temperature) parse_fast will use for this run."""
    return ModelRole(
        model=_ctx_model_fast.get() or MODEL_FAST,
        effort=_resolve_effort(_UNSET, _ctx_effort_fast, None),
        temperature=_resolve_temperature(_UNSET, _ctx_temp_fast, None),
    )


def effective_strong() -> ModelRole:
    """The (model, effort, temperature) parse_strong will use for this run."""
    return ModelRole(
        model=_ctx_model_strong.get() or MODEL_STRONG,
        effort=_resolve_effort(_UNSET, _ctx_effort_strong, EFFORT_STRONG),
        temperature=_resolve_temperature(_UNSET, _ctx_temp_strong, None),
    )


def effective_gap() -> ModelRole:
    """The (model, effort, temperature) parse_gap will use for this run."""
    return ModelRole(
        model=_ctx_model_gap.get() or MODEL_GAP,
        effort=_resolve_effort(_UNSET, _ctx_effort_gap, EFFORT_GAP),
        temperature=_resolve_temperature(_UNSET, _ctx_temp_gap, None),
    )


def effective_scoring() -> ModelRole:
    """The (model, effort, temperature) parse_scoring will use for this run."""
    return ModelRole(
        model=_ctx_model_scoring.get() or MODEL_SCORING,
        effort=_resolve_effort(_UNSET, _ctx_effort_scoring, None),
        temperature=_resolve_temperature(_UNSET, _ctx_temp_scoring, None),
    )


def effective_skills() -> ModelRole:
    """The (model, effort, temperature) parse_skills will use for this run."""
    return ModelRole(
        model=_ctx_model_skills.get() or MODEL_SKILLS,
        effort=_resolve_effort(_UNSET, _ctx_effort_skills, None),
        temperature=_resolve_temperature(_UNSET, _ctx_temp_skills, None),
    )


def parse_fast(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the fast model. Returns a ``schema`` instance."""
    model = _ctx_model_fast.get() or MODEL_FAST
    effort = _resolve_effort(_UNSET, _ctx_effort_fast, None)
    temp = _resolve_temperature(temperature, _ctx_temp_fast, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(effort, temp))


def parse_strong(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = REASONING_MAX_TOKENS,
    temperature: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the strong model.

    ``effort`` defaults to ``config.settings.EFFORT_STRONG`` (or a
    ``model_context`` override) and is forwarded to OpenRouter's unified
    reasoning parameter. Pass ``None`` to suppress reasoning entirely.

    ``temperature`` has no config.settings default - omit to let the provider
    pick, or pass an explicit value (or set ``temp_strong`` in model_context).
    """
    model = _ctx_model_strong.get() or MODEL_STRONG
    resolved = _resolve_effort(effort, _ctx_effort_strong, EFFORT_STRONG)
    temp = _resolve_temperature(temperature, _ctx_temp_strong, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, temp))


def parse_gap(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = REASONING_MAX_TOKENS,
    temperature: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the gap analyzer model.

    Uses MODEL_GAP by default. Gap analysis requires creative reframing strategy
    and strong reasoning to produce effective framing guidance, so it uses a
    more capable model than the parser/JD analyzer.

    ``effort`` defaults to ``config.settings.EFFORT_GAP`` (or a
    ``model_context`` override). ``temperature`` has no settings default -
    omit to let the provider pick, or pass an explicit value (or set
    ``temp_gap`` in model_context).
    """
    model = _ctx_model_gap.get() or MODEL_GAP
    resolved = _resolve_effort(effort, _ctx_effort_gap, EFFORT_GAP)
    temp = _resolve_temperature(temperature, _ctx_temp_gap, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, temp))


def parse_scoring(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the scoring model (recruiter panel + aggregator).

    Uses MODEL_SCORING by default, ensuring the scoring panel is independent
    of the writer model to eliminate bias.
    """
    model = _ctx_model_scoring.get() or MODEL_SCORING
    effort = _resolve_effort(_UNSET, _ctx_effort_scoring, None)
    temp = _resolve_temperature(temperature, _ctx_temp_scoring, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(effort, temp))


def parse_skills(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the skills model (categorized skill dump).

    Uses MODEL_SKILLS by default (gpt-4o-mini). No effort is forwarded by
    default - gpt-4o-mini is not a reasoning model and rejects the field.
    Pass an explicit ``effort`` (or set ``effort_skills`` in model_context)
    only when overriding to a reasoning model.
    ``max_tokens`` defaults to DEFAULT_MAX_TOKENS (not REASONING_MAX_TOKENS)
    since gpt-4o-mini caps completions at ~16k.
    """
    model = _ctx_model_skills.get() or MODEL_SKILLS
    resolved = _resolve_effort(effort, _ctx_effort_skills, None)
    temp = _resolve_temperature(temperature, _ctx_temp_skills, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, temp))
