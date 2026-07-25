"""Jobs router — all routes prefixed /jobs (mounted under /api)."""
from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from src.web.schemas import (
    CompileErrorResponse,
    JobDetail,
    JobStatus,
    JobSubmitRequest,
    JobSummary,
    SkillDumpDTO,
)
from src.web import sse as sse_module

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_summary(job) -> JobSummary:
    return JobSummary(
        job_id=job.job_id,
        label=job.label,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )


def _job_detail(job) -> JobDetail:
    return JobDetail(
        job_id=job.job_id,
        label=job.label,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        has_pdf=bool(job.output_pdf and os.path.isfile(job.output_pdf)),
        has_latex=bool(job.best_latex),
        has_skills=bool(job.output_skills and os.path.isfile(job.output_skills)),
        has_report=bool(
            job.out_dir
            and os.path.isfile(os.path.join(job.out_dir, "score_report.json"))
        ),
        aggregate_score=job.aggregate_score,
        passed=job.passed,
    )


# ---------------------------------------------------------------------------
# POST /jobs — submit a new job
# ---------------------------------------------------------------------------

@router.post("", status_code=202, response_model=JobSummary)
async def submit_job(req: JobSubmitRequest, request: Request) -> JobSummary:
    manager = request.app.state.manager
    job = manager.submit(req)
    return _job_summary(job)


# ---------------------------------------------------------------------------
# GET /jobs — list all jobs newest first
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
async def list_jobs(request: Request) -> dict:
    manager = request.app.state.manager
    jobs = sorted(manager.list(), key=lambda j: j.created_at, reverse=True)
    return {"jobs": [_job_summary(j).model_dump() for j in jobs]}


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — get job detail
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, request: Request) -> JobDetail:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_detail(job)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/events — SSE stream
# ---------------------------------------------------------------------------

@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request) -> EventSourceResponse:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    last_event_id_header = request.headers.get("last-event-id", "0")
    try:
        last_event_id = int(last_event_id_header)
    except ValueError:
        last_event_id = 0

    async def _generate():
        async for event in sse_module.event_stream(job, last_event_id):
            event_type = "progress"
            if event.stage in ("done", "failed"):
                event_type = event.stage
            yield {
                "id": str(event.seq),
                "event": event_type,
                "data": event.model_dump_json(),
            }

    response = EventSourceResponse(_generate())
    response.headers["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/latex — best LaTeX source
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
# GET /jobs/{job_id}/skills — skill dump DTO
# ---------------------------------------------------------------------------

@router.get("/{job_id}/skills", response_model=SkillDumpDTO)
async def get_skills(job_id: str, request: Request) -> SkillDumpDTO:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.output_skills:
        raise HTTPException(status_code=404, detail="Skills not available")
    if not os.path.isfile(job.output_skills):
        raise HTTPException(status_code=404, detail="Skills file not found")
    with open(job.output_skills, encoding="utf-8") as fh:
        raw = json.load(fh)
    return SkillDumpDTO(**raw)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/pdf — stream the PDF
# ---------------------------------------------------------------------------

@router.get("/{job_id}/pdf")
async def get_pdf(
    job_id: str,
    request: Request,
    download: int = 0,
) -> FileResponse:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.output_pdf:
        raise HTTPException(status_code=404, detail="PDF not available")
    if not os.path.isfile(job.output_pdf):
        raise HTTPException(status_code=404, detail="PDF file not found")

    headers: dict[str, str] = {}
    if download:
        filename = f"{job.label or job.job_id}.pdf"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(
        job.output_pdf,
        media_type="application/pdf",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/report — score report JSON
# ---------------------------------------------------------------------------

@router.get("/{job_id}/report")
async def get_report(job_id: str, request: Request) -> dict:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    report_path = (
        os.path.join(job.out_dir, "score_report.json") if job.out_dir else None
    )
    if not report_path or not os.path.isfile(report_path):
        raise HTTPException(status_code=404, detail="Score report not found")

    with open(report_path, encoding="utf-8") as fh:
        return json.load(fh)
