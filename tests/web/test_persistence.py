"""Phase: Supabase persistence write-through behavior tests.

Tests verify that JobManager and the web layer interact with ResumeRepository
correctly. All Supabase I/O is mocked — these are unit/integration tests that
don't require a real Supabase project.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.web.schemas import JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_payload(**overrides) -> dict:
    defaults = {
        "label": "PersistenceTest",
        "resume_tex": r"\documentclass{article}\begin{document}hello\end{document}",
        "jd_text": "Senior engineer role requiring Python skills.",
    }
    defaults.update(overrides)
    return defaults


def _get_app(client: AsyncClient):
    return client._transport.app  # type: ignore[attr-defined]


def _make_mock_repo() -> MagicMock:
    """Build a mock ResumeRepository with all methods stubbed."""
    repo = MagicMock()
    repo.create.return_value = None
    repo.get.return_value = None
    repo.list.return_value = []
    repo.set_status.return_value = None
    repo.save_artifacts.return_value = None
    repo.rename.return_value = None
    repo.delete.return_value = True
    repo.mark_interrupted_running.return_value = 0
    return repo


# ---------------------------------------------------------------------------
# Fixture: app with mock repo injected
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client_with_repo(monkeypatch):
    """Test client where the app's JobManager has a mock repo injected."""
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)

    mock_repo = _make_mock_repo()

    from src.web.app import create_app
    app = create_app(repo=mock_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c._mock_repo = mock_repo  # type: ignore[attr-defined]
        yield c


@pytest_asyncio.fixture
async def client_no_repo(monkeypatch):
    """Test client with no repo (Supabase disabled)."""
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)

    from src.web.app import create_app
    app = create_app(repo=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Test: submit creates a DB record via repo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_with_repo_creates_db_record(client_with_repo):
    """POST /api/jobs must call repo.create() with the new job record."""
    resp = await client_with_repo.post("/api/jobs", json=_job_payload())
    assert resp.status_code == 202

    mock_repo = client_with_repo._mock_repo
    mock_repo.create.assert_called_once()
    created_record = mock_repo.create.call_args[0][0]
    assert created_record.label == "PersistenceTest"
    assert created_record.status == "queued"


@pytest.mark.asyncio
async def test_submit_without_repo_succeeds_without_db(client_no_repo):
    """POST /api/jobs must work even when no repo is configured."""
    resp = await client_no_repo.post("/api/jobs", json=_job_payload())
    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Test: rename updates DB via repo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rename_with_repo_updates_db(client_with_repo):
    """PATCH /api/jobs/{id} must call repo.rename() when repo is configured."""
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    # repo.rename doesn't need to return anything meaningful here
    client_with_repo._mock_repo.rename.return_value = None

    resp = await client_with_repo.patch(f"/api/jobs/{job_id}", json={"label": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Renamed"

    client_with_repo._mock_repo.rename.assert_called_once_with(job_id, "Renamed")


@pytest.mark.asyncio
async def test_rename_without_repo_succeeds(client_no_repo):
    """PATCH /api/jobs/{id} must work even when no repo is configured."""
    submit = await client_no_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client_no_repo.patch(f"/api/jobs/{job_id}", json={"label": "Renamed"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: delete removes from DB via repo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_with_repo_calls_db_delete(client_with_repo):
    """DELETE /api/jobs/{id} must call repo.delete() when repo is configured."""
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client_with_repo.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204

    client_with_repo._mock_repo.delete.assert_called_once_with(job_id)


@pytest.mark.asyncio
async def test_delete_without_repo_succeeds(client_no_repo):
    """DELETE /api/jobs/{id} must work even when no repo is configured."""
    submit = await client_no_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client_no_repo.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Test: PDF served from Storage when pdf_object_key is set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_served_from_storage_when_key_set(client_with_repo, monkeypatch):
    """GET /api/jobs/{id}/pdf must stream bytes from Storage when pdf_object_key is set."""
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_with_repo)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.pdf_object_key = f"{job_id}/resume.pdf"
    job.output_pdf = None  # no local file

    fake_pdf_bytes = b"%PDF-1.4 from-storage"

    # Mock the storage download to return fake bytes
    monkeypatch.setattr(
        "src.web.routers.jobs.download_pdf_bytes",
        lambda key, client, bucket: fake_pdf_bytes,
    )

    resp = await client_with_repo.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == fake_pdf_bytes


@pytest.mark.asyncio
async def test_pdf_returns_404_when_no_key(client_no_repo):
    """GET /api/jobs/{id}/pdf returns 404 when pdf_object_key is not set."""
    submit = await client_no_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_no_repo)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    # pdf_object_key is None (default) — no Storage key means no PDF

    resp = await client_no_repo.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pdf_storage_download_failure_returns_404(client_with_repo, monkeypatch):
    """GET /api/jobs/{id}/pdf returns 404 when Storage download returns no bytes."""
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_with_repo)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.pdf_object_key = f"{job_id}/resume.pdf"

    # Storage download returns None (simulating a miss/error)
    monkeypatch.setattr(
        "src.web.routers.jobs.download_pdf_bytes",
        lambda key, client, bucket: None,
    )

    resp = await client_with_repo.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: startup calls mark_interrupted_running when repo is set
# ---------------------------------------------------------------------------

def test_mark_interrupted_running_called_on_startup():
    """App startup must call repo.mark_interrupted_running() when a repo is set."""
    mock_repo = _make_mock_repo()

    import asyncio
    from src.web.app import create_app
    from httpx import AsyncClient, ASGITransport

    app = create_app(repo=mock_repo)

    async def _run():
        # Trigger the ASGI lifespan explicitly so startup hooks run.
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/healthz")
                assert resp.status_code == 200

    asyncio.run(_run())
    mock_repo.mark_interrupted_running.assert_called_once()
