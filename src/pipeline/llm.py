"""OpenRouter client helpers for structured-output parsing.

Uses the OpenAI-compatible API at https://openrouter.ai/api/v1.
Importable with no API key present - the client is instantiated lazily and
cached, so ``require_api_key`` only fires on the first real call.
"""
import logging
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

log = logging.getLogger(__name__)

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

# Per-run extra-params overrides (Postman-style dynamic OpenRouter fields, e.g.
# temperature/top_k/top_p). Default _UNSET → no config.settings default exists
# for any role; params are omitted (provider default) unless a caller passes an
# explicit dict or model_context sets an extra_* override here.
_ctx_extra_fast: ContextVar[Any] = ContextVar("extra_fast", default=_UNSET)
_ctx_extra_strong: ContextVar[Any] = ContextVar("extra_strong", default=_UNSET)
_ctx_extra_gap: ContextVar[Any] = ContextVar("extra_gap", default=_UNSET)
_ctx_extra_scoring: ContextVar[Any] = ContextVar("extra_scoring", default=_UNSET)
_ctx_extra_skills: ContextVar[Any] = ContextVar("extra_skills", default=_UNSET)

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
    extra_fast: dict[str, Any] | None | Any = _UNSET,
    extra_strong: dict[str, Any] | None | Any = _UNSET,
    extra_gap: dict[str, Any] | None | Any = _UNSET,
    extra_scoring: dict[str, Any] | None | Any = _UNSET,
    extra_skills: dict[str, Any] | None | Any = _UNSET,
) -> Generator[list[dict], None, None]:
    """Inject model (and optional effort/extra-params) overrides for one pipeline run.

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
        extra_*: Optional Postman-style dict of additional OpenRouter request
            fields per role (temperature, top_k, top_p, ...). Omit to keep role
            defaults (no config.settings default exists for any role - the
            parameters are omitted entirely, letting the provider pick); pass
            an explicit dict to override.

    Usage::

        with model_context(fast="openai/gpt-4o-mini",
                           strong="anthropic/claude-opus-5",
                           gap="anthropic/claude-opus-5",
                           scoring="openai/gpt-4o-mini",
                           skills="openai/gpt-4o-mini",
                           effort_strong="high",
                           extra_strong={"temperature": 0.7}) as usage:
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
    t_xf = _ctx_extra_fast.set(extra_fast)
    t_xs = _ctx_extra_strong.set(extra_strong)
    t_xg = _ctx_extra_gap.set(extra_gap)
    t_xsc = _ctx_extra_scoring.set(extra_scoring)
    t_xsk = _ctx_extra_skills.set(extra_skills)
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
        _ctx_extra_fast.reset(t_xf)
        _ctx_extra_strong.reset(t_xs)
        _ctx_extra_gap.reset(t_xg)
        _ctx_extra_scoring.reset(t_xsc)
        _ctx_extra_skills.reset(t_xsk)
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
    extra_params: dict[str, Any] | None = None,
) -> SchemaT:
    extra_body: dict = {}
    if effort is not None:
        # OpenRouter's unified reasoning parameter. Anthropic models translate
        # this into a thinking-effort depth; the thinking token budget is
        # calculated from max_tokens. effort="none" is intentional: send it so
        # OpenRouter disables reasoning. Python None (omit this block) is for
        # non-reasoning models.
        extra_body["reasoning"] = {"effort": effort}
    if extra_params:
        # Postman-style dynamic params (temperature, top_k, top_p, ...) from the
        # New Application UI. None of these are native OpenAI SDK kwargs, so
        # every key rides through extra_body verbatim, merged alongside reasoning.
        extra_body.update(extra_params)
    require_parameters = effort is not None or bool(extra_params)
    if require_parameters:
        # Without this, OpenRouter may silently route to a provider that
        # doesn't support one of the fields above and just drop it - so what
        # we log as "sent" wouldn't be what the provider actually honored.
        # require_parameters forces OpenRouter to only pick providers that
        # support every parameter in this request, turning a silent mismatch
        # into a visible error instead.
        extra_body["provider"] = {"require_parameters": True}
    extra_kwargs: dict = {"extra_body": extra_body} if extra_body else {}
    log.info(
        "openrouter request | model=%s max_tokens=%d effort=%s extra_params=%s "
        "require_parameters=%s",
        model, max_tokens, effort, extra_params or {}, require_parameters,
    )
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


def _resolve_extra_params(
    explicit: Any, ctx_var: ContextVar[Any], default: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Resolve extra_params: explicit kwarg > context override > role default.

    Mirrors ``_resolve_effort``'s precedence. No role currently has a
    non-None ``default`` (extra_params isn't a config.settings constant), but
    the signature stays symmetric with ``_resolve_effort`` for consistency.
    """
    if explicit is not _UNSET:
        return explicit  # type: ignore[return-value]
    ctx = ctx_var.get()
    if ctx is not _UNSET:
        return ctx  # may be None or {} - both mean "nothing to forward"
    return default


def _optional_kwargs(
    effort: str | None, extra_params: dict[str, Any] | None
) -> dict[str, Any]:
    """Build the effort/extra_params kwargs for `_parse`, omitting unset values.

    Centralizes the "only forward what's actually set" rule so every parse_*
    role resolves the same way, whether the role has a reasoning default or not.
    """
    kwargs: dict[str, Any] = {}
    if effort is not None:
        kwargs["effort"] = effort
    if extra_params:
        kwargs["extra_params"] = extra_params
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
    """The (model, effort, extra_params) parse_fast will use for this run."""
    return ModelRole(
        model=_ctx_model_fast.get() or MODEL_FAST,
        effort=_resolve_effort(_UNSET, _ctx_effort_fast, None),
        extra_params=_resolve_extra_params(_UNSET, _ctx_extra_fast, None),
    )


def effective_strong() -> ModelRole:
    """The (model, effort, extra_params) parse_strong will use for this run."""
    return ModelRole(
        model=_ctx_model_strong.get() or MODEL_STRONG,
        effort=_resolve_effort(_UNSET, _ctx_effort_strong, EFFORT_STRONG),
        extra_params=_resolve_extra_params(_UNSET, _ctx_extra_strong, None),
    )


def effective_gap() -> ModelRole:
    """The (model, effort, extra_params) parse_gap will use for this run."""
    return ModelRole(
        model=_ctx_model_gap.get() or MODEL_GAP,
        effort=_resolve_effort(_UNSET, _ctx_effort_gap, EFFORT_GAP),
        extra_params=_resolve_extra_params(_UNSET, _ctx_extra_gap, None),
    )


def effective_scoring() -> ModelRole:
    """The (model, effort, extra_params) parse_scoring will use for this run."""
    return ModelRole(
        model=_ctx_model_scoring.get() or MODEL_SCORING,
        effort=_resolve_effort(_UNSET, _ctx_effort_scoring, None),
        extra_params=_resolve_extra_params(_UNSET, _ctx_extra_scoring, None),
    )


def effective_skills() -> ModelRole:
    """The (model, effort, extra_params) parse_skills will use for this run."""
    return ModelRole(
        model=_ctx_model_skills.get() or MODEL_SKILLS,
        effort=_resolve_effort(_UNSET, _ctx_effort_skills, None),
        extra_params=_resolve_extra_params(_UNSET, _ctx_extra_skills, None),
    )


def parse_fast(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extra_params: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the fast model. Returns a ``schema`` instance."""
    model = _ctx_model_fast.get() or MODEL_FAST
    effort = _resolve_effort(_UNSET, _ctx_effort_fast, None)
    extra = _resolve_extra_params(extra_params, _ctx_extra_fast, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(effort, extra))


def parse_strong(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = REASONING_MAX_TOKENS,
    extra_params: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the strong model.

    ``effort`` defaults to ``config.settings.EFFORT_STRONG`` (or a
    ``model_context`` override) and is forwarded to OpenRouter's unified
    reasoning parameter. Pass ``None`` to suppress reasoning entirely.

    ``extra_params`` has no config.settings default - omit to let the provider
    pick, or pass an explicit dict (or set ``extra_strong`` in model_context).
    """
    model = _ctx_model_strong.get() or MODEL_STRONG
    resolved = _resolve_effort(effort, _ctx_effort_strong, EFFORT_STRONG)
    extra = _resolve_extra_params(extra_params, _ctx_extra_strong, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, extra))


def parse_gap(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = REASONING_MAX_TOKENS,
    extra_params: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the gap analyzer model.

    Uses MODEL_GAP by default. Gap analysis requires creative reframing strategy
    and strong reasoning to produce effective framing guidance, so it uses a
    more capable model than the parser/JD analyzer.

    ``effort`` defaults to ``config.settings.EFFORT_GAP`` (or a
    ``model_context`` override). ``extra_params`` has no settings default -
    omit to let the provider pick, or pass an explicit dict (or set
    ``extra_gap`` in model_context).
    """
    model = _ctx_model_gap.get() or MODEL_GAP
    resolved = _resolve_effort(effort, _ctx_effort_gap, EFFORT_GAP)
    extra = _resolve_extra_params(extra_params, _ctx_extra_gap, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, extra))


def parse_scoring(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extra_params: Any = _UNSET,
) -> SchemaT:
    """Structured parse on the scoring model (recruiter panel + aggregator).

    Uses MODEL_SCORING by default, ensuring the scoring panel is independent
    of the writer model to eliminate bias.
    """
    model = _ctx_model_scoring.get() or MODEL_SCORING
    effort = _resolve_effort(_UNSET, _ctx_effort_scoring, None)
    extra = _resolve_extra_params(extra_params, _ctx_extra_scoring, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(effort, extra))


def parse_skills(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: Any = _UNSET,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extra_params: Any = _UNSET,
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
    extra = _resolve_extra_params(extra_params, _ctx_extra_skills, None)
    return _parse(system, user, schema, model, max_tokens, **_optional_kwargs(resolved, extra))
