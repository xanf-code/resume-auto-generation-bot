"""Jobs router - all routes prefixed /jobs (mounted under /api)."""
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
# Helpers
# ---------------------------------------------------------------------------

def _resolve_verdict(job, report: dict | None) -> tuple[float | None, bool | None]:
    """Resolve (aggregate_score, passed) from the job, falling back to *report*.

    The in-memory fields are cleared on a server restart, so a job that finished
    earlier keeps its verdict only on disk. Reading it back here lets the list
    endpoint serve score badges without the client opening each job's detail.
    """
    aggregate_score = job.aggregate_score
    passed = job.passed
    if report is not None:
        if aggregate_score is None and isinstance(report.get("aggregate_score"), (int, float)):
            aggregate_score = report["aggregate_score"]
        if passed is None and isinstance(report.get("passed"), bool):
            passed = report["passed"]
    return aggregate_score, passed


def _job_summary(job) -> JobSummary:
    aggregate_score, passed = _resolve_verdict(job, _load_report(job))
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
    )


def _resolve_package_file(job, filename: str) -> str | None:
    """Return an on-disk path to *filename* in the job's emit package, or None.

    ``emit`` writes deliverables to a per-JD package folder
    (``out_dir/{jd_name}/``), collapsing to ``out_dir`` itself only when no
    ``jd_name`` is set. A caller that looks only at ``out_dir/{filename}``
    therefore misses the file for every web job - which always carries a
    ``jd_name`` (``JobManager`` sets it from the label). Resolve the nested
    layout so all deliverables (skills, score report) are found consistently.
    """
    if not job.out_dir:
        return None
    candidates: list[str] = []
    if job.jd_name:
        candidates.append(os.path.join(job.out_dir, job.jd_name, filename))
    candidates.append(os.path.join(job.out_dir, filename))
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Last resort: a single package folder under out_dir, in case the on-disk
    # jd_name differs from the in-memory value (emit's per-JD layout).
    try:
        for name in os.listdir(job.out_dir):
            nested = os.path.join(job.out_dir, name, filename)
            if os.path.isfile(nested):
                return nested
    except OSError:
        pass
    return None


def _resolve_skills_path(job) -> str | None:
    """Return an on-disk skills.json path for *job*, or None.

    Prefers ``job.output_skills`` when set, then falls back to the per-JD
    package layout via :func:`_resolve_package_file`.
    """
    if job.output_skills and os.path.isfile(job.output_skills):
        return job.output_skills
    return _resolve_package_file(job, "skills.json")


def _load_report(job) -> dict | None:
    """Parse ``score_report.json`` from the job's emit package, or None.

    Resolves the per-JD package layout (``out_dir/{jd_name}/score_report.json``)
    - the path ``emit`` actually writes - via :func:`_resolve_package_file`,
    not just ``out_dir`` directly. Tolerates a missing or malformed file so the
    panel simply stays empty rather than 500-ing the whole detail request.
    """
    path = _resolve_package_file(job, "score_report.json")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


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
    # The recruiter verdict lives on disk in score_report.json. Read it here so
    # a job opened after it finished (SSE never replays to a done job) - or after
    # a server restart that cleared the in-memory score fields - still shows the
    # panel's scores instead of an empty "recruiters weigh in" placeholder.
    report = _load_report(job)
    aggregate_score, passed = _resolve_verdict(job, report)
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
        has_pdf=bool(job.output_pdf and os.path.isfile(job.output_pdf)),
        has_latex=bool(job.best_latex),
        has_skills=bool(_resolve_skills_path(job)),
        has_report=report is not None,
        aggregate_score=aggregate_score,
        passed=passed,
        persona_scores=persona_scores,
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
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not manager.cancel(job_id):
        raise HTTPException(status_code=409, detail="Job already finished")
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
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=404, detail="Skills not available")
    skills_path = _resolve_skills_path(job)
    if not skills_path:
        raise HTTPException(status_code=404, detail="Skills not available")
    with open(skills_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return SkillDumpDTO(**raw)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/pdf - stream the PDF
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
# GET /jobs/{job_id}/report - score report JSON
# ---------------------------------------------------------------------------

@router.get("/{job_id}/report")
async def get_report(job_id: str, request: Request) -> dict:
    manager = request.app.state.manager
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    report_path = _resolve_package_file(job, "score_report.json")
    if not report_path:
        raise HTTPException(status_code=404, detail="Score report not found")

    with open(report_path, encoding="utf-8") as fh:
        return json.load(fh)
