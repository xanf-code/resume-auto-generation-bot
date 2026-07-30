"""Phase 10 RED tests - POST /api/compile route tests."""
from __future__ import annotations

import os
import tempfile

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
    monkeypatch.setattr("src.web.app._build_repo", lambda: None)
    from src.web.app import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


_MINIMAL_TEX = r"\documentclass{article}\begin{document}hello\end{document}"


# ---------------------------------------------------------------------------
# Test 1: Successful compile → 200 application/pdf
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_success_returns_pdf(client, monkeypatch, tmp_path):
    """Monkeypatched compile_tex returns ok=True with a real file."""
    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake content")

    monkeypatch.setattr(
        "src.web.routers.compile.compile_tex",
        lambda tex_source, workdir, timeout=60: (True, str(fake_pdf), []),
    )

    resp = await client.post("/api/compile", json={"resume_tex": _MINIMAL_TEX})
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Test 2: Compile failure → 422 with error list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_failure_returns_422(client, monkeypatch):
    """Monkeypatched compile_tex returns ok=False with error messages."""
    monkeypatch.setattr(
        "src.web.routers.compile.compile_tex",
        lambda tex_source, workdir, timeout=60: (
            False,
            None,
            ["l.42: undefined control sequence"],
        ),
    )

    resp = await client.post("/api/compile", json={"resume_tex": _MINIMAL_TEX})
    assert resp.status_code == 422
    body = resp.json()
    # FastAPI wraps HTTPException detail in body
    detail = body.get("detail", body)
    assert detail["ok"] is False
    assert "l.42" in detail["errors"][0]


# ---------------------------------------------------------------------------
# Test 3: Integration - real tectonic compile (skip if not installed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_compile_real_tectonic(client):
    """Actually calls tectonic - skip if not installed on PATH."""
    import shutil
    if shutil.which("tectonic") is None:
        pytest.skip("tectonic not installed")

    resp = await client.post("/api/compile", json={"resume_tex": _MINIMAL_TEX})
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
