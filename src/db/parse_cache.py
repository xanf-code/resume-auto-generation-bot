"""ResumeParseCacheRepository — PostgREST wrapper for the resume_parse_cache table.

Caches the deterministic ``parse_resume`` output (``ResumeStruct`` +
``IdentityLedger``) keyed by a sha256 hash of the raw resume .tex, so an
identical resume across separate job runs skips the parser LLM call entirely.

``InMemoryResumeParseCacheRepository`` implements the same get/store surface
backed by a dict — used when Supabase is not configured (tests / offline), so
``parse_resume`` always has a single cache backend as source of truth.
"""
from __future__ import annotations

from typing import Any

from src.db.config import DbSettings

TABLE = "resume_parse_cache"


class ResumeParseCacheRepository:
    """Cache interface for the ``resume_parse_cache`` Postgres table via Supabase."""

    TABLE = TABLE

    def __init__(self, client: Any, settings: DbSettings) -> None:
        self._client = client
        self._settings = settings

    def get(self, resume_hash: str) -> dict | None:
        """Return the cached payload dict for *resume_hash*, or ``None`` if absent."""
        resp = (
            self._client.table(self.TABLE)
            .select("payload")
            .eq("resume_hash", resume_hash)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0]["payload"]

    def store(self, resume_hash: str, payload: dict) -> None:
        """Upsert *payload* for *resume_hash*."""
        row = {"resume_hash": resume_hash, "payload": payload}
        self._client.table(self.TABLE).upsert(row).execute()


class InMemoryResumeParseCacheRepository:
    """Dict-backed stand-in for ``ResumeParseCacheRepository``."""

    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    def get(self, resume_hash: str) -> dict | None:
        return self._rows.get(resume_hash)

    def store(self, resume_hash: str, payload: dict) -> None:
        self._rows[resume_hash] = payload


_repo: Any = None


def get_parse_cache_repo() -> Any:
    """Lazy singleton: Supabase-backed repo when configured, else in-memory.

    Cached at module level (like ``src.db.client.get_client``) so repeated
    ``parse_resume`` calls within one process reuse the same backend.
    """
    global _repo
    if _repo is None:
        from src.db.config import try_load_db_settings

        settings = try_load_db_settings()
        if settings is not None:
            from src.db.client import get_client

            _repo = ResumeParseCacheRepository(get_client(settings), settings)
        else:
            _repo = InMemoryResumeParseCacheRepository()
    return _repo


def reset_parse_cache_repo() -> None:
    """Clear the cached repo singleton (testing only)."""
    global _repo
    _repo = None
