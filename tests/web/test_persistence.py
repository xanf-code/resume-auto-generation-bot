"""Phase: repository-backed persistence (SSOT) behavior tests.

Tests verify that JobManager and the web layer read/write through
ResumeRepository. Supabase I/O uses mocks or InMemoryResumeRepository —
no real Supabase project required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.db.models import JobRecord
from src.db.repository import InMemoryResumeRepository
from tests.web.conftest import seed_job_done


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
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client_with_repo(monkeypatch):
    """Test client with InMemoryResumeRepository (SSOT for functional CRUD)."""
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)

    repo = InMemoryResumeRepository()
    from src.web.app import create_app
    app = create_app(repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c._repo = repo  # type: ignore[attr-defined]
        yield c


@pytest_asyncio.fixture
async def client_default(monkeypatch):
    """Test client using create_app() default (InMemory when no Supabase env)."""
    monkeypatch.setattr("src.web.job_manager.run_job", lambda job, mgr: None)
    monkeypatch.setattr("src.web.app._build_repo", lambda: None)

    from src.web.app import create_app
    app = create_app(repo=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Submit / rename / delete via repository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_persists_to_repo(client_with_repo):
    """POST /api/jobs must create a row that list/get can read back."""
    resp = await client_with_repo.post("/api/jobs", json=_job_payload())
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    repo = client_with_repo._repo
    rec = repo.get(job_id)
    assert rec is not None
    assert rec.label == "PersistenceTest"
    assert rec.status == "queued"


@pytest.mark.asyncio
async def test_submit_works_with_default_inmemory_repo(client_default):
    """POST /api/jobs works when create_app falls back to InMemoryResumeRepository."""
    resp = await client_default.post("/api/jobs", json=_job_payload())
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_rename_updates_repo(client_with_repo):
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client_with_repo.patch(f"/api/jobs/{job_id}", json={"label": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Renamed"
    assert client_with_repo._repo.get(job_id).label == "Renamed"


@pytest.mark.asyncio
async def test_delete_removes_from_repo(client_with_repo):
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client_with_repo.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204
    assert client_with_repo._repo.get(job_id) is None


@pytest.mark.asyncio
async def test_external_repo_delete_reflected_on_list_without_restart(client_with_repo):
    """Deleting via the repository (simulating a Supabase dashboard delete)
    must make the job disappear from GET /api/jobs without restarting the app.
    """
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    listed = await client_with_repo.get("/api/jobs")
    assert any(j["job_id"] == job_id for j in listed.json()["jobs"])

    # Simulate external delete (e.g. row removed in Supabase UI).
    assert client_with_repo._repo.delete(job_id) is True

    listed_after = await client_with_repo.get("/api/jobs")
    ids = [j["job_id"] for j in listed_after.json()["jobs"]]
    assert job_id not in ids

    detail = await client_with_repo.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 404


# ---------------------------------------------------------------------------
# PDF served from Storage key on the repository row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_served_from_storage_when_key_set(client_with_repo, monkeypatch):
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_with_repo)
    seed_job_done(
        app.state.manager,
        job_id,
        pdf_object_key=f"{job_id}/resume.pdf",
    )

    fake_pdf_bytes = b"%PDF-1.4 from-storage"
    monkeypatch.setattr(
        "src.web.routers.jobs.download_pdf_bytes",
        lambda key, client, bucket: fake_pdf_bytes,
    )

    resp = await client_with_repo.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == fake_pdf_bytes


@pytest.mark.asyncio
async def test_pdf_returns_404_when_no_key(client_default):
    submit = await client_default.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_default)
    seed_job_done(app.state.manager, job_id)

    resp = await client_default.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pdf_storage_download_failure_returns_404(client_with_repo, monkeypatch):
    submit = await client_with_repo.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app(client_with_repo)
    seed_job_done(
        app.state.manager,
        job_id,
        pdf_object_key=f"{job_id}/resume.pdf",
    )

    monkeypatch.setattr(
        "src.web.routers.jobs.download_pdf_bytes",
        lambda key, client, bucket: None,
    )

    resp = await client_with_repo.get(f"/api/jobs/{job_id}/pdf")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def test_mark_interrupted_running_called_on_startup():
    """App startup must call repo.mark_interrupted_running() when a repo is set."""
    mock_repo = _make_mock_repo()

    import asyncio
    from src.web.app import create_app
    from httpx import AsyncClient, ASGITransport

    app = create_app(repo=mock_repo)

    async def _run():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/healthz")
                assert resp.status_code == 200

    asyncio.run(_run())
    mock_repo.mark_interrupted_running.assert_called_once()


def test_inmemory_mark_interrupted_running():
    repo = InMemoryResumeRepository()
    now = datetime.now(timezone.utc)
    repo.create(JobRecord(job_id="a", label="A", status="queued", created_at=now))
    repo.create(JobRecord(job_id="b", label="B", status="running", created_at=now))
    repo.create(JobRecord(job_id="c", label="C", status="done", created_at=now))

    n = repo.mark_interrupted_running()
    assert n == 2
    assert repo.get("a").status == "failed"
    assert repo.get("b").status == "failed"
    assert repo.get("c").status == "done"
