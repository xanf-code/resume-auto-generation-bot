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

from config.settings import MODEL_FAST, MODEL_STRONG, require_api_key

SchemaT = TypeVar("SchemaT", bound=BaseModel)

DEFAULT_MAX_TOKENS = 16000

# Per-run model overrides — set by model_context(); default to None (→ config constants).
_ctx_model_fast: ContextVar[str | None] = ContextVar("model_fast", default=None)
_ctx_model_strong: ContextVar[str | None] = ContextVar("model_strong", default=None)

# Accumulates raw usage dicts [{model, input_tokens, output_tokens}] when set.
_ctx_usage: ContextVar[list | None] = ContextVar("usage", default=None)


@contextmanager
def model_context(
    fast: str, strong: str
) -> Generator[list[dict], None, None]:
    """Inject model overrides and collect token usage for one pipeline run.

    Usage::

        with model_context(fast="google/gemini-2.5-flash",
                           strong="anthropic/claude-sonnet-4-6") as usage:
            run_pipeline(...)
        cost = compute_cost(usage)
    """
    t_fast = _ctx_model_fast.set(fast)
    t_strong = _ctx_model_strong.set(strong)
    usage: list[dict] = []
    t_usage = _ctx_usage.set(usage)
    try:
        yield usage
    finally:
        _ctx_model_fast.reset(t_fast)
        _ctx_model_strong.reset(t_strong)
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
) -> SchemaT:
    response = client().beta.chat.completions.parse(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=schema,
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
    effort: str = "high",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the strong model.

    ``effort`` is accepted for call-site compatibility but not forwarded;
    OpenRouter does not support this Anthropic-specific parameter.
    """
    model = _ctx_model_strong.get() or MODEL_STRONG
    return _parse(system, user, schema, model, max_tokens)
