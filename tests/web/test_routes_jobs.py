"""Phase 10 RED tests - HTTP route tests for /api/jobs endpoints."""
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


@pytest.mark.asyncio
async def test_get_skills_falls_back_to_package_on_disk(client, tmp_path):
    """When output_skills is unset (LangGraph channel drop), discover skills.json."""
    submit = await client.post("/api/jobs", json=_job_payload(label="vestwell"))
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.output_skills = None  # simulate the dropped-channel bug
    job.out_dir = str(tmp_path / job_id)
    job.jd_name = "vestwell"

    pkg = tmp_path / job_id / "vestwell"
    pkg.mkdir(parents=True)
    (pkg / "skills.json").write_text(
        json.dumps(
            {
                "language_and_framework": ["TypeScript"],
                "infrastructure": ["AWS"],
                "database": [],
                "ai_tools": [],
            }
        ),
        encoding="utf-8",
    )

    resp = await client.get(f"/api/jobs/{job_id}/skills")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["language_and_framework"] == ["TypeScript"]

    detail = await client.get(f"/api/jobs/{job_id}")
    assert detail.json()["has_skills"] is True


# ---------------------------------------------------------------------------
# Test 8b: GET /api/jobs/{id} on a DONE job surfaces the recruiter panel's
# scores straight from score_report.json - so a job opened after it finished
# (or after a server restart) still shows a verdict, not an empty panel.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_detail_includes_persona_scores_from_report(client, tmp_path):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.out_dir = str(tmp_path / job_id)
    os.makedirs(job.out_dir)
    # In-memory score fields dropped (e.g. after a restart) - must fall back to disk.
    job.aggregate_score = None
    job.passed = None

    report = {
        "passed": True,
        "aggregate_score": 87.625,
        "personas": [
            {
                "persona": "ATS Matcher",
                "keyword_match": 90,
                "impact_quality": 85,
                "coherence": 90,
                "plausibility": 95,
                "formatting": 80,
                "notes": "Solid keyword coverage.",
            },
            {
                "persona": "Skeptic",
                "keyword_match": 85,
                "impact_quality": 75,
                "coherence": 80,
                "plausibility": 65,
                "formatting": 90,
                "notes": "Some claims need backing.",
            },
        ],
    }
    with open(os.path.join(job.out_dir, "score_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)

    resp = await client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["has_report"] is True
    assert body["aggregate_score"] == 87.625
    assert body["passed"] is True

    scores = body["persona_scores"]
    assert scores is not None
    assert [s["persona"] for s in scores] == ["ATS Matcher", "Skeptic"]
    assert scores[0]["keyword_match"] == 90
    assert scores[0]["notes"] == "Solid keyword coverage."


# ---------------------------------------------------------------------------
# Test 8c: GET /api/jobs (the list endpoint) carries the recruiter verdict on
# each summary, falling back to score_report.json when the in-memory fields are
# gone. Without this the home grid/rail render finished jobs with no score badge
# until the user opens each one's detail.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_includes_verdict_from_report(client, tmp_path):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.out_dir = str(tmp_path / job_id)
    os.makedirs(job.out_dir)
    # In-memory score fields dropped (e.g. after a restart) - must fall back to disk.
    job.aggregate_score = None
    job.passed = None
    with open(os.path.join(job.out_dir, "score_report.json"), "w", encoding="utf-8") as f:
        json.dump({"passed": True, "aggregate_score": 87.625}, f)

    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    summary = next(j for j in resp.json()["jobs"] if j["job_id"] == job_id)

    assert summary["aggregate_score"] == 87.625
    assert summary["passed"] is True


# ---------------------------------------------------------------------------
# Test 8d: emit writes the report to the per-JD PACKAGE folder
# (``out_dir/{jd_name}/score_report.json``), not ``out_dir`` directly. The
# report loader must resolve that nested layout - the same way the skills loader
# already does - or the detail panel and list badge stay empty for every real
# web job (which always carries a jd_name = label).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_resolved_from_per_jd_package_dir(client, tmp_path):
    submit = await client.post("/api/jobs", json=_job_payload(label="TestJob"))
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.jd_name = "TestJob"
    job.out_dir = str(tmp_path / job_id)
    job.aggregate_score = None
    job.passed = None
    # Write where emit actually writes: out_dir/{jd_name}/score_report.json.
    pkg_dir = os.path.join(job.out_dir, job.jd_name)
    os.makedirs(pkg_dir)
    report = {
        "passed": True,
        "aggregate_score": 91.0,
        "personas": [
            {
                "persona": "ATS Matcher",
                "keyword_match": 90,
                "impact_quality": 88,
                "coherence": 92,
                "plausibility": 95,
                "formatting": 90,
                "notes": "Strong coverage.",
            }
        ],
    }
    with open(os.path.join(pkg_dir, "score_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)

    # Detail panel: persona scores + verdict resolve from the nested package.
    detail = (await client.get(f"/api/jobs/{job_id}")).json()
    assert detail["has_report"] is True
    assert detail["aggregate_score"] == 91.0
    assert detail["passed"] is True
    assert [s["persona"] for s in detail["persona_scores"]] == ["ATS Matcher"]

    # List badge: same verdict, same nested resolution.
    listed = next(
        j for j in (await client.get("/api/jobs")).json()["jobs"]
        if j["job_id"] == job_id
    )
    assert listed["aggregate_score"] == 91.0
    assert listed["passed"] is True

    # Raw report endpoint resolves the nested package too.
    raw = await client.get(f"/api/jobs/{job_id}/report")
    assert raw.status_code == 200
    assert raw.json()["aggregate_score"] == 91.0


@pytest.mark.asyncio
async def test_get_detail_without_report_has_no_scores(client, tmp_path):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    job.status = JobStatus.DONE
    job.out_dir = str(tmp_path / job_id)
    os.makedirs(job.out_dir)

    resp = await client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_report"] is False
    assert body["persona_scores"] is None


# ---------------------------------------------------------------------------
# Test 9: PATCH /api/jobs/{id} renames label
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rename_job_updates_label(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client.patch(f"/api/jobs/{job_id}", json={"label": "  New Label  "})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "New Label"
    assert body["job_id"] == job_id

    detail = await client.get(f"/api/jobs/{job_id}")
    assert detail.json()["label"] == "New Label"


@pytest.mark.asyncio
async def test_rename_unknown_job_returns_404(client):
    resp = await client.patch("/api/jobs/missing-id", json={"label": "Nope"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rename_blank_label_returns_422(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]
    resp = await client.patch(f"/api/jobs/{job_id}", json={"label": "   "})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test 10: DELETE /api/jobs/{id} removes job + artifacts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_job_returns_204_and_removes(client, tmp_path):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    job = app.state.manager.get(job_id)
    out_dir = tmp_path / job_id
    out_dir.mkdir()
    (out_dir / "marker.txt").write_text("x")
    job.out_dir = str(out_dir)

    resp = await client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204

    assert app.state.manager.get(job_id) is None
    assert not out_dir.exists()

    list_resp = await client.get("/api/jobs")
    ids = [j["job_id"] for j in list_resp.json()["jobs"]]
    assert job_id not in ids


@pytest.mark.asyncio
async def test_delete_unknown_job_returns_404(client):
    resp = await client.delete("/api/jobs/missing-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 11: POST /api/jobs/{id}/cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_queued_job_returns_202_and_sets_event(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    resp = await client.post(f"/api/jobs/{job_id}/cancel")
    assert resp.status_code == 202

    app = _get_app_from_client(client)
    assert app.state.manager.get(job_id).cancel_event.is_set()


@pytest.mark.asyncio
async def test_cancel_unknown_job_returns_404(client):
    resp = await client.post("/api/jobs/missing-id/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_finished_job_returns_409(client):
    submit = await client.post("/api/jobs", json=_job_payload())
    job_id = submit.json()["job_id"]

    app = _get_app_from_client(client)
    app.state.manager.get(job_id).status = JobStatus.DONE

    resp = await client.post(f"/api/jobs/{job_id}/cancel")
    assert resp.status_code == 409
