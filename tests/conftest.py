"""Shared pytest configuration for the full test suite."""
from __future__ import annotations

import pytest

from src.db.parse_cache import reset_parse_cache_repo


@pytest.fixture(autouse=True)
def _reset_parse_cache_repo(monkeypatch):
    """Isolate the parse-cache singleton between tests and keep it off the network.

    Without the reset, two tests parsing the same resume text (same sha256
    hash) would leak a cache HIT from one test into the next, silently
    skipping the LLM-mock path the second test expects to exercise. Without
    clearing the Supabase env vars, ``get_parse_cache_repo`` would build a
    real ``ResumeParseCacheRepository`` from this repo's local ``.env``
    (loaded via ``config.settings`` at import time) and hit the network for
    every parser test - mirroring how other web tests already force
    ``_build_repo`` to ``None`` to stay offline by default.
    """
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    reset_parse_cache_repo()
    yield
    reset_parse_cache_repo()
