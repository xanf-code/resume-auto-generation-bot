"""Anthropic client helpers for structured-output parsing.

Importable with no API key present — the client is instantiated lazily and
cached, so ``require_api_key`` only fires on the first real call.
"""
from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from config.settings import MODEL_FAST, MODEL_STRONG, require_api_key

SchemaT = TypeVar("SchemaT", bound=BaseModel)

DEFAULT_MAX_TOKENS = 16000


@lru_cache(maxsize=1)
def client() -> anthropic.Anthropic:
    """Return a cached Anthropic client (validates the API key on first call)."""
    return anthropic.Anthropic(api_key=require_api_key())


def _extract_parsed(message, schema: type[SchemaT]) -> SchemaT:
    """Pull the parsed schema instance out of a ParsedMessage's content blocks.

    The SDK attaches the validated model to ``parsed_output`` on each parsed
    text block. We return the first non-null instance.
    """
    for block in message.content:
        parsed = getattr(block, "parsed_output", None)
        if isinstance(parsed, schema):
            return parsed
        if parsed is not None:
            return schema.model_validate(parsed)
    raise ValueError(
        f"No parsed {schema.__name__} instance found in model response."
    )


def parse_fast(
    system: str,
    user: str,
    schema: type[SchemaT],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the fast (Haiku) model. Returns a ``schema`` instance."""
    message = client().messages.parse(
        model=MODEL_FAST,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    return _extract_parsed(message, schema)


def parse_strong(
    system: str,
    user: str,
    schema: type[SchemaT],
    effort: str = "high",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SchemaT:
    """Structured parse on the strong (Opus) model with adaptive thinking.

    No temperature/top_p — those are rejected on Opus 4.8.
    """
    message = client().messages.parse(
        model=MODEL_STRONG,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )
    return _extract_parsed(message, schema)
