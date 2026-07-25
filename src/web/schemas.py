"""API-boundary DTOs for the resume-bot web layer.

All models use Pydantic v2. Validators run at the boundary; downstream code
can trust the values are sane. No pipeline logic lives here.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, computed_field, field_validator


# ---------------------------------------------------------------------------
# Inbound request models
# ---------------------------------------------------------------------------

class JobSubmitRequest(BaseModel):
    """Body for POST /api/jobs."""

    label: str
    resume_tex: str
    jd_text: str
    enable_scoring: bool = False

    @field_validator("label")
    @classmethod
    def _label_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("label must not be blank")
        return stripped

    @field_validator("resume_tex", "jd_text")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class JobRenameRequest(BaseModel):
    """Body for PATCH /api/jobs/{id} — update display label."""

    label: str

    @field_validator("label")
    @classmethod
    def _label_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("label must not be blank")
        return stripped


class CompileRequest(BaseModel):
    """Body for POST /api/compile (raw tectonic compile)."""

    resume_tex: str

    @field_validator("resume_tex")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("resume_tex must not be blank")
        return v


# ---------------------------------------------------------------------------
# Outbound response models
# ---------------------------------------------------------------------------

class PersonaScoreDTO(BaseModel):
    """One recruiter persona's scores — mirrors PanelScore from pipeline."""

    persona: str
    keyword_match: int
    impact_quality: int
    coherence: int
    plausibility: int
    formatting: int
    notes: str


class ProgressEvent(BaseModel):
    """A single SSE frame sent to subscribers of a running job."""

    job_id: str
    seq: int = 0
    stage: str
    human_label: str
    pct: int
    iteration: int = 1
    aggregate_score: float | None = None
    passed: bool | None = None
    persona_scores: list[PersonaScoreDTO] | None = None
    # Populated only on a terminal ``failed`` frame so clients can surface the
    # reason (e.g. a user abort) directly from the stream.
    error: str | None = None


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class JobSummary(BaseModel):
    """Lightweight job representation for the job rail listing.

    Carries the recruiter verdict (``aggregate_score``/``passed``) so the job
    rail and home grid can render score badges directly from the list endpoint,
    without opening each job's detail to backfill them.
    """

    job_id: str
    label: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    aggregate_score: float | None = None
    passed: bool | None = None


class JobDetail(JobSummary):
    """Extended job info including artifact presence flags."""

    has_pdf: bool = False
    has_latex: bool = False
    has_skills: bool = False
    has_report: bool = False
    persona_scores: list[PersonaScoreDTO] | None = None


class CompileErrorResponse(BaseModel):
    """Response body when POST /api/compile fails."""

    ok: bool = False
    errors: list[str]


class SkillDumpDTO(BaseModel):
    """Four skill buckets with a computed total — mirrors SkillDump."""

    language_and_framework: list[str] = []
    infrastructure: list[str] = []
    database: list[str] = []
    ai_tools: list[str] = []

    @computed_field
    @property
    def total(self) -> int:
        return (
            len(self.language_and_framework)
            + len(self.infrastructure)
            + len(self.database)
            + len(self.ai_tools)
        )
