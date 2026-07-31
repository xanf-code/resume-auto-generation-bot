"""Tests for ResumeParseCacheRepository - uses a fully mocked Supabase client."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.db.config import DbSettings
from src.db.parse_cache import (
    InMemoryResumeParseCacheRepository,
    ResumeParseCacheRepository,
    get_parse_cache_repo,
    reset_parse_cache_repo,
)


def _settings() -> DbSettings:
    return DbSettings(url="https://example.supabase.co", service_key="fake-key")


def _make_repo(client=None) -> tuple[ResumeParseCacheRepository, MagicMock]:
    if client is None:
        client = MagicMock()
    repo = ResumeParseCacheRepository(client=client, settings=_settings())
    return repo, client


def _mock_table(client: MagicMock) -> MagicMock:
    return client.table.return_value


# ---------------------------------------------------------------------------
# ResumeParseCacheRepository (Supabase, mocked client)
# ---------------------------------------------------------------------------

def test_get_returns_none_when_not_cached():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    result = repo.get("abc123")

    client.table.assert_called_with(ResumeParseCacheRepository.TABLE)
    table.select.return_value.eq.assert_called_with("resume_hash", "abc123")
    assert result is None


def test_get_returns_payload_when_cached():
    repo, client = _make_repo()
    table = _mock_table(client)
    payload = {"resume_struct": {"roles": []}, "identity_ledger": {"name": "Jane"}}
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"payload": payload}]
    )

    result = repo.get("abc123")

    assert result == payload


def test_store_calls_upsert_with_hash_and_payload():
    repo, client = _make_repo()
    table = _mock_table(client)
    table.upsert.return_value.execute.return_value = MagicMock(data=[{}])
    payload = {"resume_struct": {"roles": []}, "identity_ledger": {"name": "Jane"}}

    repo.store("abc123", payload)

    client.table.assert_called_with(ResumeParseCacheRepository.TABLE)
    table.upsert.assert_called_once_with({"resume_hash": "abc123", "payload": payload})


# ---------------------------------------------------------------------------
# InMemoryResumeParseCacheRepository
# ---------------------------------------------------------------------------

def test_inmemory_get_miss_then_store_then_hit():
    repo = InMemoryResumeParseCacheRepository()
    payload = {"resume_struct": {"roles": []}, "identity_ledger": {"name": "Jane"}}

    assert repo.get("abc123") is None

    repo.store("abc123", payload)

    assert repo.get("abc123") == payload


def test_inmemory_never_returns_payload_for_a_different_hash():
    repo = InMemoryResumeParseCacheRepository()
    repo.store("hash-a", {"resume_struct": {}, "identity_ledger": {}})

    assert repo.get("hash-b") is None


# ---------------------------------------------------------------------------
# get_parse_cache_repo() lazy singleton
# ---------------------------------------------------------------------------

def test_get_parse_cache_repo_falls_back_to_in_memory_without_supabase_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    reset_parse_cache_repo()

    repo = get_parse_cache_repo()

    assert isinstance(repo, InMemoryResumeParseCacheRepository)
    reset_parse_cache_repo()


def test_get_parse_cache_repo_is_a_singleton():
    reset_parse_cache_repo()
    first = get_parse_cache_repo()
    second = get_parse_cache_repo()

    assert first is second
    reset_parse_cache_repo()


def test_get_parse_cache_repo_builds_supabase_repo_when_configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    reset_parse_cache_repo()

    fake_client = MagicMock()
    monkeypatch.setattr("src.db.client.get_client", lambda settings: fake_client)

    repo = get_parse_cache_repo()

    assert isinstance(repo, ResumeParseCacheRepository)
    reset_parse_cache_repo()
