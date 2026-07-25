"""API-boundary DTOs for the resume-bot web layer.

All models use Pydantic v2. Validators run at the boundary; downstream code
can trust the values are sane. No pipeline logic lives here.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Inbound request models
# ---------------------------------------------------------------------------

class RubricWeightsDTO(BaseModel):
    """The five rubric-dimension weights, each in [0, 1].

    A model-level validator normalizes the five so they sum to 1.0 - the
    aggregate is compared against ``threshold`` on a 0–100 scale, so the weights
    MUST be normalized for the threshold semantics to hold. An all-zero payload
    is rejected (nothing to normalize).
    """

    keyword_match: float = Field(ge=0.0, le=1.0)
    impact_quality: float = Field(ge=0.0, le=1.0)
    coherence: float = Field(ge=0.0, le=1.0)
    plausibility: float = Field(ge=0.0, le=1.0)
    formatting: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _normalize_to_unit_sum(self) -> "RubricWeightsDTO":
        total = (
            self.keyword_match + self.impact_quality + self.coherence
            + self.plausibility + self.formatting
        )
        if total <= 0:
            raise ValueError("rubric weights must not all be zero")
        # object.__setattr__ isn't needed - models are mutable by default here.
        self.keyword_match /= total
        self.impact_quality /= total
        self.coherence /= total
        self.plausibility /= total
        self.formatting /= total
        return self


class TuningDTO(BaseModel):
    """Per-application pipeline tuning knobs (see docs/phase-1-tuning-backend.md).

    Range clamps are enforced at the boundary so downstream pipeline code can
    trust the values. ``to_tuning`` converts to the internal
    :class:`~src.pipeline.tuning.PipelineTuning`.
    """

    threshold: int = Field(ge=0, le=100)
    plausibility_floor: int = Field(ge=0, le=100)
    max_iterations: int = Field(ge=1, le=8)
    max_compile_retries: int = Field(ge=0, le=5)
    max_identity_retries: int = Field(ge=0, le=5)
    max_length_retries: int = Field(ge=0, le=6)
    rubric_weights: RubricWeightsDTO

    def to_tuning(self):
        """Convert to the internal PipelineTuning dataclass."""
        from src.pipeline.tuning import PipelineTuning

        return PipelineTuning(
            threshold=self.threshold,
            plausibility_floor=self.plausibility_floor,
            max_iterations=self.max_iterations,
            max_compile_retries=self.max_compile_retries,
            max_identity_retries=self.max_identity_retries,
            max_length_retries=self.max_length_retries,
            rubric_weights={
                "keyword_match": self.rubric_weights.keyword_match,
                "impact_quality": self.rubric_weights.impact_quality,
                "coherence": self.rubric_weights.coherence,
                "plausibility": self.rubric_weights.plausibility,
                "formatting": self.rubric_weights.formatting,
            },
        )


class JobSubmitRequest(BaseModel):
    """Body for POST /api/jobs."""

    label: str
    resume_tex: str
    jd_text: str
    enable_scoring: bool = False
    tuning: TuningDTO | None = None

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
    """Body for PATCH /api/jobs/{id} - update display label."""

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
    """One recruiter persona's scores - mirrors PanelScore from pipeline."""

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
    """Four skill buckets with a computed total - mirrors SkillDump."""

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
