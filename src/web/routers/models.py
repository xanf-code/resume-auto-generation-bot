"""OpenRouter models catalog proxy - GET /api/models.

Fetches the public OpenRouter model list, keeps a short in-process TTL cache,
and returns a slim DTO the New Application UI needs for model + reasoning
effort pickers. The pipeline uses structured outputs, so models without
``structured_outputs`` / ``response_format`` are filtered out.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/models", tags=["models"])

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE_TTL_SECONDS = 3600


class ModelCatalogEntry(BaseModel):
    id: str
    name: str
    structured_output: bool = True
    reasoning: dict[str, Any] | None = None


class ModelsCatalogResponse(BaseModel):
    models: list[ModelCatalogEntry]


class _Cache:
    """Tiny in-process TTL cache for the slim catalog."""

    def __init__(self) -> None:
        self.payload: list[ModelCatalogEntry] | None = None
        self.expires_at: float = 0.0

    def clear(self) -> None:
        self.payload = None
        self.expires_at = 0.0

    def get(self) -> list[ModelCatalogEntry] | None:
        if self.payload is not None and time.monotonic() < self.expires_at:
            return self.payload
        return None

    def set(self, payload: list[ModelCatalogEntry]) -> None:
        self.payload = payload
        self.expires_at = time.monotonic() + CACHE_TTL_SECONDS


_cache = _Cache()


def _supports_structured_output(raw: dict[str, Any]) -> bool:
    params = raw.get("supported_parameters") or []
    return "structured_outputs" in params or "response_format" in params


def _slim_reasoning(raw_reasoning: Any) -> dict[str, Any] | None:
    """Map OpenRouter's reasoning object into the UI-facing shape.

    - ``None`` / missing → no reasoning.
    - Object with ``supported_efforts`` key (list or null) → include it.
    - Object without ``supported_efforts`` → reasoning without effort selector
      (omit the key so the UI hides the effort dropdown).
    """
    if not isinstance(raw_reasoning, dict):
        return None

    out: dict[str, Any] = {
        "mandatory": bool(raw_reasoning.get("mandatory", False)),
    }
    if "default_effort" in raw_reasoning:
        out["default_effort"] = raw_reasoning.get("default_effort")

    if "supported_efforts" in raw_reasoning:
        efforts = raw_reasoning["supported_efforts"]
        if efforts is None:
            out["supported_efforts"] = None
        elif isinstance(efforts, list):
            out["supported_efforts"] = [str(e) for e in efforts]
        # else: ignore malformed
    # else: omit supported_efforts entirely (no effort selector)

    return out


def slim_models(raw_data: list[dict[str, Any]]) -> list[ModelCatalogEntry]:
    """Filter + slim OpenRouter model rows into catalog entries."""
    entries: list[ModelCatalogEntry] = []
    for raw in raw_data:
        if not _supports_structured_output(raw):
            continue
        mid = raw.get("id")
        if not mid:
            continue
        entries.append(
            ModelCatalogEntry(
                id=str(mid),
                name=str(raw.get("name") or mid),
                structured_output=True,
                reasoning=_slim_reasoning(raw.get("reasoning")),
            )
        )
    entries.sort(key=lambda m: m.name.lower())
    return entries


async def fetch_openrouter_models() -> list[dict[str, Any]]:
    """HTTP fetch of OpenRouter's public models list."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(OPENROUTER_MODELS_URL)
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data")
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Malformed OpenRouter models response")
    return data


@router.get("", response_model=ModelsCatalogResponse)
async def list_models() -> ModelsCatalogResponse:
    """Return the cached slim OpenRouter catalog (refresh on miss/expiry)."""
    cached = _cache.get()
    if cached is not None:
        return ModelsCatalogResponse(models=cached)

    try:
        raw = await fetch_openrouter_models()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch OpenRouter models: {exc}"
        ) from exc

    slim = slim_models(raw)
    _cache.set(slim)
    return ModelsCatalogResponse(models=slim)
