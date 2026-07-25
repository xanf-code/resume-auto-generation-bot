"""Phase 10 RED tests — HTTP route tests for /api/jobs endpoints."""
from __future__ import annotations

import json
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.web.schemas import JobStatus


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(monkeypatch):
    """Async HTTP test client with pipeline stubbed out."""
    # Patch the name in job_manager's namespace (where submit() looks it up).
    # Patching src.web.runner.run_job alone doesn't work because job_manager
    # imported run_job directly via "from src.web.runner import run_job".
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)
    from src.web.app import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_payload(**overrides) -> dict:
    defaults = {
        "label": "TestJob",
        "resume_tex": r"\documentclass{article}\begin{document}hello\end{document}",
        "jd_text": "Senior engineer role requiring Python and FastAPI skills.",
    }
    defaults.update(overrides)
    return defaults


def _get_app_from_client(client: AsyncClient):
    """Extract the ASGI app from the httpx client transport."""
    return client._transport.app  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 1: POST /api/jobs → 202 with job fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_job_returns_202(client):
    resp = await client.post("/api/jobs", json=_job_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["label"] == "TestJob"
    assert body["status"] == "queued"


# ---------------------------------------------------------------------------
# Test 2: POST /api/jobs with blank resume_tex → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_blank_resume_tex_returns_422(client):
    resp = await client.post("/api/jobs", json=_job_payload(resume_tex="   "))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test 3: GET /api/jobs → 200 with jobs list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_returns_list(client):
    await client.post("/api/jobs", json=_job_payload())
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert "jobs" in body
    assert isinstance(body["jobs"], list)
    assert len(body["jobs"]) >= 1


# ---------------------------------------------------------------------------
# Test 4: GET /api/jobs/{unknown_id} → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_unknown_job_returns_404(client):
    resp = await client.get("/api/jobs/nonexistent-job-id-12345")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 5: GET /api/jobs/{id}/latex on a QUEUED job → 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latex_queued_job_returns_409(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client.get(f"/api/jobs/{job_id}/latex")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Test 6: GET /api/jobs/{id}/latex on a DONE job → 200 with latex
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latex_done_job_returns_200(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    assert job is not None

    job.status = JobStatus.DONE
    job.best_latex = r"\documentclass{article}\begin{document}best\end{document}"

    resp = await client.get(f"/api/jobs/{job_id}/latex")
    assert resp.status_code == 200
    body = resp.json()
    assert "latex" in body
    assert "best" in body["latex"]


# ---------------------------------------------------------------------------
# Test 7: GET /api/jobs/{id}/pdf on DONE job with real temp PDF → 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pdf_done_job_returns_200(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf content")
        pdf_path = f.name

    try:
        app = _get_app_from_client(client)
        job = app.state.manager.get(job_id)
        job.status = JobStatus.DONE
        job.output_pdf = pdf_path

        resp = await client.get(f"/api/jobs/{job_id}/pdf")
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
    finally:
        os.unlink(pdf_path)


# ---------------------------------------------------------------------------
# Test 8: GET /api/jobs/{id}/skills on DONE job with valid JSON → 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_skills_done_job_returns_200(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    skills_data = {
        "language_and_framework": ["Python"],
        "infrastructure": [],
        "database": [],
        "ai_tools": [],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(skills_data, f)
        skills_path = f.name

    try:
        app = _get_app_from_client(client)
        job = app.state.manager.get(job_id)
        job.status = JobStatus.DONE
        job.output_skills = skills_path

        resp = await client.get(f"/api/jobs/{job_id}/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert "Python" in body["language_and_framework"]
    finally:
        os.unlink(skills_path)
