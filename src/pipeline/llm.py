"""OpenRouter client helpers for structured-output parsing.

Uses the OpenAI-compatible API at https://openrouter.ai/api/v1.
Importable with no API key present — the client is instantiated lazily and
cached, so ``require_api_key`` only fires on the first real call.
"""
from functools import lru_cache
from typing import TypeVar

import openai
from pydantic import BaseModel

from config.settings import MODEL_FAST, MODEL_STRONG, require_api_key

SchemaT = TypeVar("SchemaT", bound=BaseModel)

DEFAULT_MAX_TOKENS = 16000


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
    """Structured parse on the fast (Haiku) model. Returns a ``schema`` instance."""
    return _parse(system, user, schema, MODEL_FAST, max_tokens)


def parse_strong(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: str = "high",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the strong (Opus) model.

    ``effort`` is accepted for call-site compatibility but not forwarded;
    OpenRouter does not support this Anthropic-specific parameter.
    """
    return _parse(system, user, schema, MODEL_STRONG, max_tokens)
