"""Phase 10 RED tests - GET /api/healthz endpoint tests."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(monkeypatch):
    """Async HTTP test client with pipeline execution stubbed out."""
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)
    from src.web.app import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: With OPENROUTER_API_KEY set → api_key_present: true
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_healthz_with_api_key(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key-present")
    resp = await client.get("/api/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_present"] is True


# ---------------------------------------------------------------------------
# Test 2: Without OPENROUTER_API_KEY → api_key_present: false
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_healthz_without_api_key(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resp = await client.get("/api/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_present"] is False


# ---------------------------------------------------------------------------
# Test 3: Response contains required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_healthz_required_fields(client):
    resp = await client.get("/api/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "active_jobs" in body
    assert "max_concurrent" in body


# ---------------------------------------------------------------------------
# Test 4: API key value is NEVER in response body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_healthz_api_key_not_leaked(client, monkeypatch):
    secret = "sk-super-secret-key-do-not-leak"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    resp = await client.get("/api/healthz")
    assert resp.status_code == 200
    body_text = resp.text
    assert secret not in body_text
    # Also check the parsed JSON doesn't contain the secret
    body = resp.json()
    for value in body.values():
        assert str(value) != secret
