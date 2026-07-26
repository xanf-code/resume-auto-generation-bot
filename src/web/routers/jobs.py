"""Jobs router - all routes prefixed /jobs (mounted under /api)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

try:
    from src.db.storage import download_pdf_bytes
except ImportError:
    download_pdf_bytes = None  # type: ignore[assignment]

from src.web.schemas import (
    CompileErrorResponse,
    JobDetail,
    JobRenameRequest,
    JobStatus,
    JobSubmitRequest,
    JobSummary,
    PersonaScoreDTO,
    SkillDumpDTO,
)
from src.web import sse as sse_module

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Helpers — repository-backed job views only (no disk reads)
# ---------------------------------------------------------------------------

def _resolve_verdict(job) -> tuple[float | None, bool | None]:
    """Resolve (aggregate_score, passed) from repository-backed job fields."""
    aggregate_score = job.aggregate_score
    passed = job.passed
    # Fall back to score_report for rows that predate dedicated columns.
    report = job.score_report
    if report is not None:
        if aggregate_score is None and isinstance(report.get("aggregate_score"), (int, float)):
            aggregate_score = report["aggregate_score"]
        if passed is None and isinstance(report.get("passed"), bool):
            passed = report["passed"]
    return aggregate_score, passed


def _job_summary(job) -> JobSummary:
    aggregate_score, passed = _resolve_verdict(job)
    return JobSummary(
        job_id=job.job_id,
        label=job.label,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        aggregate_score=aggregate_score,
        passed=passed,
        role=job.role,
        domains=job.domains,
    )


def _persona_scores_from_report(report: dict) -> list[PersonaScoreDTO] | None:
    """Map the report's ``personas`` array to DTOs, skipping malformed entries."""
    personas = report.get("personas")
    if not isinstance(personas, list):
        return None
    scores: list[PersonaScoreDTO] = []
    for entry in personas:
        if not isinstance(entry, dict):
            continue
        try:
            scores.append(PersonaScoreDTO(**entry))
        except Exception:
            continue
    return scores or None


def _job_detail(job) -> JobDetail:
    # Verdict and persona scores come from the repository-backed score_report.
    report = job.score_report
    aggregate_score, passed = _resolve_verdict(job)
    persona_scores: list[PersonaScoreDTO] | None = None
    if report is not None:
        persona_scores = _persona_scores_from_report(report)

    return JobDetail(
        job_id=job.job_id,
        label=job.label,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        has_pdf=bool(job.pdf_object_key),
        has_latex=bool(job.best_latex),
        has_skills=job.output_skills is not None,
        has_report=report is not None,
        aggregate_score=aggregate_score,
        passed=passed,
        persona_scores=persona_scores,
        role=job.role,
        domains=job.domains,
    )


# ---------------------------------------------------------------------------
# POST /jobs - submit a new job
# ---------------------------------------------------------------------------

@router.post("", status_code=202, response_model=JobSummary)
async def submit_job(req: JobSubmitRequest, request: Request) -> JobSummary:
    manager = request.app.state.manager
    job = manager.submit(req)
    return _job_summary(job)


# ---------------------------------------------------------------------------
# GET /jobs - list all jobs newest first
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
async def list_jobs(request: Request) -> dict:
    manager = request.app.state.manager
    jobs = sorted(manager.list(), key=lambda j: j.created_at, reverse=True)
    return {"jobs": [_job_summary(j).model_dump() for j in jobs]}


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} - get job detail
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, request: Request) -> JobDetail:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_detail(job)


# ---------------------------------------------------------------------------
# PATCH /jobs/{job_id} - rename (update label)
# ---------------------------------------------------------------------------

@router.patch("/{job_id}", response_model=JobSummary)
async def rename_job(
    job_id: str,
    req: JobRenameRequest,
    request: Request,
) -> JobSummary:
    manager = request.app.state.manager
    job = manager.rename(job_id, req.label)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_summary(job)


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/cancel - request abort of a running job
# ---------------------------------------------------------------------------

@router.post("/{job_id}/cancel", status_code=202, response_model=JobSummary)
async def cancel_job(job_id: str, request: Request) -> JobSummary:
    manager = request.app.state.manager
    if manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not manager.cancel(job_id):
        raise HTTPException(status_code=409, detail="Job already finished")
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_summary(job)


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id} - remove job + artifacts
# ---------------------------------------------------------------------------

@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request) -> Response:
    manager = request.app.state.manager
    deleted = manager.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/events - SSE stream
# ---------------------------------------------------------------------------

@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    from src.web.schemas import ProgressEvent

    manager = request.app.state.manager
    stored = manager.get(job_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Job not found")

    last_event_id_header = request.headers.get("last-event-id", "0")
    try:
        last_event_id = int(last_event_id_header)
    except ValueError:
        last_event_id = 0

    runtime = manager.get_runtime(job_id)

    async def _generate():
        if runtime is not None:
            async for event in sse_module.event_stream(runtime, last_event_id):
                event_type = "progress"
                if event.stage in ("done", "failed"):
                    event_type = event.stage
                yield {
                    "id": str(event.seq),
                    "event": event_type,
                    "data": event.model_dump_json(),
                }
            return

        # No live runtime (finished run / post-restart): one synthetic terminal.
        if stored.status == JobStatus.DONE:
            stage = "done"
        else:
            stage = "failed"
        terminal = ProgressEvent(
            job_id=job_id,
            stage=stage,
            human_label="Done" if stage == "done" else "Failed",
            pct=100 if stage == "done" else 0,
            seq=max(last_event_id + 1, 1),
            aggregate_score=stored.aggregate_score,
            passed=stored.passed,
            detail=(
                "Run complete - artifacts ready"
                if stage == "done"
                else (stored.error or "Unknown error.")
            ),
            error=None if stage == "done" else stored.error,
        )
        yield {
            "id": str(terminal.seq),
            "event": stage,
            "data": terminal.model_dump_json(),
        }

    response = EventSourceResponse(_generate())
    response.headers["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/latex - best LaTeX source
# ---------------------------------------------------------------------------

@router.get("/{job_id}/latex")
async def get_latex(job_id: str, request: Request) -> dict:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail="Job is not done yet")
    return {"latex": job.best_latex}


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/skills - skill dump DTO
# ---------------------------------------------------------------------------

@router.get("/{job_id}/skills", response_model=SkillDumpDTO)
async def get_skills(job_id: str, request: Request) -> SkillDumpDTO:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or job.output_skills is None:
        raise HTTPException(status_code=404, detail="Skills not available")
    return SkillDumpDTO(**job.output_skills)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/pdf - stream the PDF
# ---------------------------------------------------------------------------

@router.get("/{job_id}/pdf")
async def get_pdf(
    job_id: str,
    request: Request,
    download: int = 0,
):
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.pdf_object_key or download_pdf_bytes is None:
        raise HTTPException(status_code=404, detail="PDF not available")

    headers: dict[str, str] = {}
    if download:
        filename = f"{job.label or job.job_id}.pdf"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    # Resolve client+bucket from env; pass None when unconfigured so tests
    # can monkeypatch download_pdf_bytes without real Supabase creds.
    _client = None
    _bucket = "resumes"
    from src.web.config import _optional_db_settings
    from src.db.client import get_client
    db_settings = _optional_db_settings()
    if db_settings is not None:
        _client = get_client(db_settings)
        _bucket = db_settings.bucket

    data = await run_in_threadpool(
        download_pdf_bytes, job.pdf_object_key, _client, _bucket
    )
    if not data:
        raise HTTPException(status_code=404, detail="PDF not available")

    return Response(content=data, media_type="application/pdf", headers=headers)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/report - score report JSON
# ---------------------------------------------------------------------------

@router.get("/{job_id}/report")
async def get_report(job_id: str, request: Request) -> dict:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.score_report is None:
        raise HTTPException(status_code=404, detail="Score report not found")
    return job.score_report
