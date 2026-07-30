"""Lazy singleton Supabase client factory.

The client is created on first call to ``get_client`` and cached per URL so
test fixtures can easily swap it out by clearing ``_CACHE``.
"""
from __future__ import annotations

from typing import Any

from src.db.config import DbSettings

_CACHE: dict[str, Any] = {}


def get_client(settings: DbSettings) -> Any:
    """Return a cached ``supabase.Client`` for the given settings URL.

    Creates a new client on first call; subsequent calls with the same URL
    return the cached instance.
    """
    if settings.url not in _CACHE:
        from supabase import create_client
        _CACHE[settings.url] = create_client(settings.url, settings.service_key)
    return _CACHE[settings.url]


def clear_cache() -> None:
    """Clear the client cache (useful for testing)."""
    _CACHE.clear()
