"""OpenRouter client helpers for structured-output parsing.

Uses the OpenAI-compatible API at https://openrouter.ai/api/v1.
Importable with no API key present — the client is instantiated lazily and
cached, so ``require_api_key`` only fires on the first real call.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Generator, TypeVar

import openai
from pydantic import BaseModel

from config.settings import (
    EFFORT_GAP,
    EFFORT_STRONG,
    MODEL_FAST,
    MODEL_GAP,
    MODEL_SCORING,
    MODEL_STRONG,
    require_api_key,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Sized just under gpt-4o-mini's real 16,384-token output ceiling
# (MODEL_FAST / MODEL_SCORING) — do not raise this without checking that cap.
DEFAULT_MAX_TOKENS = 16000
# MODEL_STRONG / MODEL_GAP are Anthropic reasoning models whose extended-
# thinking tokens bill against the SAME completion budget as the structured
# output. DEFAULT_MAX_TOKENS is too tight for them — reasoning alone can eat
# the ceiling before the schema is emitted, surfacing as
# openai.LengthFinishReasonError. These two calls get more headroom.
REASONING_MAX_TOKENS = 32000

# Per-run model overrides — set by model_context(); default to None (→ config constants).
_ctx_model_fast: ContextVar[str | None] = ContextVar("model_fast", default=None)
_ctx_model_strong: ContextVar[str | None] = ContextVar("model_strong", default=None)
_ctx_model_gap: ContextVar[str | None] = ContextVar("model_gap", default=None)
_ctx_model_scoring: ContextVar[str | None] = ContextVar("model_scoring", default=None)

# Accumulates raw usage dicts [{model, input_tokens, output_tokens}] when set.
_ctx_usage: ContextVar[list | None] = ContextVar("usage", default=None)


@contextmanager
def model_context(
    fast: str, strong: str, gap: str | None = None, scoring: str | None = None
) -> Generator[list[dict], None, None]:
    """Inject model overrides and collect token usage for one pipeline run.

    Args:
        fast: Model for extraction (parser, JD analyzer).
        strong: Model for writer.
        gap: Model for gap analyzer (creative reframing strategy).
             Defaults to ``strong`` if not provided.
        scoring: Model for scoring panel (recruiters + aggregator).
                 Defaults to ``fast`` if not provided.

    Usage::

        with model_context(fast="openai/gpt-4o-mini",
                           strong="anthropic/claude-opus-5",
                           gap="anthropic/claude-opus-5",
                           scoring="openai/gpt-4o-mini") as usage:
            run_pipeline(...)
        cost = compute_cost(usage)
    """
    t_fast = _ctx_model_fast.set(fast)
    t_strong = _ctx_model_strong.set(strong)
    t_gap = _ctx_model_gap.set(gap or strong)
    t_scoring = _ctx_model_scoring.set(scoring or fast)
    usage: list[dict] = []
    t_usage = _ctx_usage.set(usage)
    try:
        yield usage
    finally:
        _ctx_model_fast.reset(t_fast)
        _ctx_model_strong.reset(t_strong)
        _ctx_model_gap.reset(t_gap)
        _ctx_model_scoring.reset(t_scoring)
        _ctx_usage.reset(t_usage)


@lru_cache(maxsize=1)
def client() -> openai.OpenAI:
    """Return a cached OpenRouter client (validates the API key on first call)."""
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=require_api_key(),
    )


def _parse(
    system: str,
    user: str,
    schema: type[SchemaT],
    model: str,
    max_tokens: int,
    effort: str | None = None,
) -> SchemaT:
    extra_kwargs = {}
    if effort is not None:
        # OpenRouter's unified reasoning parameter — not a native OpenAI SDK
        # field, so it must go through extra_body. Anthropic reasoning models
        # translate this into a thinking-effort depth; the thinking token
        # budget itself is calculated from max_tokens.
        extra_kwargs["extra_body"] = {"reasoning": {"effort": effort}}
    response = client().beta.chat.completions.parse(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=schema,
        **extra_kwargs,
    )
    usage_log = _ctx_usage.get()
    if usage_log is not None and response.usage:
        usage_log.append({
            "model": model,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        })
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise ValueError(
            f"No parsed {schema.__name__} instance found in model response."
        )
    return parsed


def parse_fast(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the fast model. Returns a ``schema`` instance."""
    model = _ctx_model_fast.get() or MODEL_FAST
    return _parse(system, user, schema, model, max_tokens)


def parse_strong(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: str = EFFORT_STRONG,
    max_tokens: int = REASONING_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the strong model.

    ``effort`` defaults to ``config.settings.EFFORT_STRONG`` and is forwarded
    to OpenRouter's unified reasoning parameter — change it in settings to
    retune reasoning depth without touching call sites.
    """
    model = _ctx_model_strong.get() or MODEL_STRONG
    return _parse(system, user, schema, model, max_tokens, effort=effort)


def parse_gap(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: str = EFFORT_GAP,
    max_tokens: int = REASONING_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the gap analyzer model.

    Uses MODEL_GAP by default. Gap analysis requires creative reframing strategy
    and strong reasoning to produce effective framing guidance, so it uses a
    more capable model than the parser/JD analyzer.

    ``effort`` defaults to ``config.settings.EFFORT_GAP`` and is forwarded to
    OpenRouter's unified reasoning parameter — change it in settings to
    retune reasoning depth without touching call sites.
    """
    model = _ctx_model_gap.get() or MODEL_GAP
    return _parse(system, user, schema, model, max_tokens, effort=effort)


def parse_scoring(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the scoring model (recruiter panel + aggregator).

    Uses MODEL_SCORING by default, ensuring the scoring panel is independent
    of the writer model to eliminate bias.
    """
    model = _ctx_model_scoring.get() or MODEL_SCORING
    return _parse(system, user, schema, model, max_tokens)
