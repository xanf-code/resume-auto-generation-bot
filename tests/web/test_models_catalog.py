"""GET /api/models - OpenRouter catalog proxy with slim reasoning DTO."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Minimal OpenRouter-shaped payload. Only models with structured_outputs /
# response_format should appear in the slim catalog.
OPENROUTER_PAYLOAD = {
    "data": [
        {
            "id": "anthropic/claude-opus-5",
            "name": "Claude Opus 5",
            "supported_parameters": [
                "reasoning",
                "response_format",
                "structured_outputs",
            ],
            "reasoning": {
                "mandatory": False,
                "default_enabled": True,
                "supported_efforts": ["max", "xhigh", "high", "medium", "low"],
                "default_effort": "high",
            },
        },
        {
            "id": "openai/gpt-4o-mini",
            "name": "GPT-4o Mini",
            "supported_parameters": [
                "response_format",
                "structured_outputs",
                "temperature",
            ],
            "reasoning": None,
        },
        {
            "id": "google/gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "supported_parameters": ["reasoning", "response_format", "structured_outputs"],
            # Reasoning without an effort selector (supported_efforts omitted).
            "reasoning": {"mandatory": True},
        },
        {
            "id": "openai/o4-mini",
            "name": "o4 Mini",
            "supported_parameters": ["reasoning", "response_format", "structured_outputs"],
            # null supported_efforts → all gateway efforts accepted.
            "reasoning": {
                "mandatory": False,
                "supported_efforts": None,
                "default_effort": "medium",
            },
        },
        {
            "id": "some/no-structured-output",
            "name": "No Structured Output",
            "supported_parameters": ["temperature"],
            "reasoning": None,
        },
    ]
}


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)
    monkeypatch.setattr("src.web.app._build_repo", lambda: None)
    # Fresh cache for every test.
    from src.web.routers import models as models_router

    models_router._cache.clear()

    fetch_calls = {"n": 0}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return OPENROUTER_PAYLOAD

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url: str, **kwargs):
            fetch_calls["n"] += 1
            assert "openrouter.ai/api/v1/models" in url
            return FakeResponse()

    monkeypatch.setattr(models_router.httpx, "AsyncClient", FakeAsyncClient)

    from src.web.app import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, fetch_calls


@pytest.mark.asyncio
async def test_models_returns_slim_catalog(client):
    c, _ = client
    resp = await c.get("/api/models")
    assert resp.status_code == 200
    body = resp.json()
    assert "models" in body
    ids = [m["id"] for m in body["models"]]
    assert "anthropic/claude-opus-5" in ids
    assert "openai/gpt-4o-mini" in ids
    assert "some/no-structured-output" not in ids

    opus = next(m for m in body["models"] if m["id"] == "anthropic/claude-opus-5")
    assert opus["name"] == "Claude Opus 5"
    assert opus["structured_output"] is True
    assert opus["reasoning"]["supported_efforts"] == [
        "max",
        "xhigh",
        "high",
        "medium",
        "low",
    ]
    assert opus["reasoning"]["default_effort"] == "high"
    assert opus["reasoning"]["mandatory"] is False


@pytest.mark.asyncio
async def test_models_reasoning_null_when_unsupported(client):
    c, _ = client
    resp = await c.get("/api/models")
    mini = next(m for m in resp.json()["models"] if m["id"] == "openai/gpt-4o-mini")
    assert mini["reasoning"] is None


@pytest.mark.asyncio
async def test_models_reasoning_without_effort_selector(client):
    """supported_efforts key omitted → reasoning object with supported_efforts absent."""
    c, _ = client
    resp = await c.get("/api/models")
    gemini = next(m for m in resp.json()["models"] if m["id"] == "google/gemini-2.5-pro")
    assert gemini["reasoning"] is not None
    assert gemini["reasoning"]["mandatory"] is True
    assert "supported_efforts" not in gemini["reasoning"]


@pytest.mark.asyncio
async def test_models_null_supported_efforts_preserved(client):
    c, _ = client
    resp = await c.get("/api/models")
    o4 = next(m for m in resp.json()["models"] if m["id"] == "openai/o4-mini")
    assert o4["reasoning"]["supported_efforts"] is None


@pytest.mark.asyncio
async def test_models_sorted_by_name(client):
    c, _ = client
    resp = await c.get("/api/models")
    names = [m["name"] for m in resp.json()["models"]]
    assert names == sorted(names, key=str.lower)


@pytest.mark.asyncio
async def test_models_cache_avoids_second_fetch(client):
    c, fetch_calls = client
    assert (await c.get("/api/models")).status_code == 200
    assert fetch_calls["n"] == 1
    assert (await c.get("/api/models")).status_code == 200
    assert fetch_calls["n"] == 1
