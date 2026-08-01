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


_KNOWN_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
)

# Keys the dedicated `effort` field (or _parse's own request-shaping logic)
# already owns - reject them from extra_params so there's exactly one way to
# set them, with no risk of an extra_params entry silently overriding/
# shadowing a field the backend manages itself. `provider` is reserved because
# _parse always sets provider.require_parameters=True whenever effort or
# extra_params is present - see src.pipeline.llm._parse.
_RESERVED_PARAM_KEYS = frozenset({"effort", "reasoning", "model", "provider"})


class ModelRoleDTO(BaseModel):
    """One LLM role: OpenRouter model slug + optional reasoning effort + params.

    ``extra_params`` is a Postman-style, open bag of additional OpenRouter
    request fields (temperature, top_k, top_p, seed, ...) the New Application
    UI lets users attach per role via a key/value editor. Every entry rides
    straight into the outgoing request body - see
    ``src.pipeline.llm._parse``.
    """

    model: str
    effort: str | None = None
    extra_params: dict[str, float | int | str | bool] | None = None

    @field_validator("model")
    @classmethod
    def _model_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("model must not be blank")
        return stripped

    @field_validator("effort")
    @classmethod
    def _effort_known_or_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in _KNOWN_EFFORTS:
            raise ValueError(
                f"effort must be one of {sorted(_KNOWN_EFFORTS)}, got {v!r}"
            )
        return v

    @field_validator("extra_params")
    @classmethod
    def _extra_params_valid(
        cls, v: dict[str, float | int | str | bool] | None
    ) -> dict[str, float | int | str | bool] | None:
        if not v:
            return None
        cleaned: dict[str, float | int | str | bool] = {}
        for key, value in v.items():
            stripped = key.strip()
            if not stripped:
                raise ValueError("extra_params keys must not be blank")
            if stripped in _RESERVED_PARAM_KEYS:
                raise ValueError(
                    f"extra_params key {stripped!r} is reserved; "
                    "use the dedicated field instead"
                )
            cleaned[stripped] = value
        return cleaned


class ModelsDTO(BaseModel):
    """Per-application model overrides for the five user-facing LLM roles.

    ``skills`` defaults when omitted so older clients that only sent
    writer/parser/gap/scoring keep working.
    """

    writer: ModelRoleDTO
    parser: ModelRoleDTO
    gap: ModelRoleDTO
    scoring: ModelRoleDTO
    skills: ModelRoleDTO | None = None

    def to_pipeline_models(self):
        """Convert to the internal PipelineModels dataclass."""
        from config import settings
        from src.pipeline.models import ModelRole, PipelineModels

        skills = self.skills or ModelRoleDTO(model=settings.MODEL_SKILLS, effort=None)
        return PipelineModels(
            writer=ModelRole(self.writer.model, self.writer.effort, self.writer.extra_params),
            parser=ModelRole(self.parser.model, self.parser.effort, self.parser.extra_params),
            gap=ModelRole(self.gap.model, self.gap.effort, self.gap.extra_params),
            skills=ModelRole(skills.model, skills.effort, skills.extra_params),
            scoring=ModelRole(self.scoring.model, self.scoring.effort, self.scoring.extra_params),
        )


class JobSubmitRequest(BaseModel):
    """Body for POST /api/jobs."""

    label: str
    resume_tex: str
    jd_text: str
    enable_scoring: bool = False
    tuning: TuningDTO | None = None
    models: ModelsDTO | None = None
    bullet_shapes: list[str] | None = None
    # Obsidian vault "learning" toggle - when False, this run skips retrieval
    # of proven examples and vault tuning overrides (the run note is still
    # always written). Defaults True; the UI exposes this as an opt-out.
    obsidian_learn: bool = True

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

    @field_validator("bullet_shapes")
    @classmethod
    def _validate_bullet_shapes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            return None
        from src.prompts.writer import SHAPE_NAMES
        unknown = [name for name in v if name not in SHAPE_NAMES]
        if unknown:
            raise ValueError(f"unknown bullet shape names: {unknown!r}")
        # Deduplicate while preserving first-occurrence order
        seen: set[str] = set()
        deduped: list[str] = []
        for name in v:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped


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
    # A concrete, human-readable line describing what this node actually did -
    # e.g. "Compile failed - sending LaTeX errors back to the writer". Drives
    # the live activity feed under the stepper; None when a node has nothing
    # notable to say.
    detail: str | None = None
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
    # JD classification (role/domain tag) - None/empty until classification runs.
    role: str | None = None
    domains: list[str] = Field(default_factory=list)


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
