"""Pydantic models — the typed vocabulary of the pipeline.

Every model sets ``extra="forbid"`` so its JSON schema emits
``additionalProperties: false`` (required by ``messages.parse`` structured
output). Numeric bound constraints (ge/le) are intentionally omitted to keep
schemas flat and SDK-compatible — range validation happens in application code.
"""
from pydantic import BaseModel, ConfigDict

_STRICT = ConfigDict(extra="forbid")


class Role(BaseModel):
    """A single employment position — the atomic identity unit."""

    model_config = _STRICT

    company: str
    title: str
    start: str
    end: str


class IdentityLedger(BaseModel):
    """Immutable source of truth for identity fields.

    The renderer injects these locked values; no writer output can alter them.
    """

    model_config = _STRICT

    name: str
    contact: str
    roles: list[Role]


class ResumeRole(BaseModel):
    """A parsed role: ledger identity fields plus the original bullet evidence."""

    model_config = _STRICT

    company: str
    title: str
    start: str
    end: str
    source_evidence: list[str]


class ResumeStruct(BaseModel):
    """Structured extraction of the source resume."""

    model_config = _STRICT

    roles: list[ResumeRole]
    education: list[str]
    skills: list[str]


class SkillWeight(BaseModel):
    """A skill with its importance weight (0-1, validated in code)."""

    model_config = _STRICT

    name: str
    weight: float


class JDVector(BaseModel):
    """Structured representation of the target job description."""

    model_config = _STRICT

    weighted_skills: list[SkillWeight]
    ats_keywords: list[str]
    seniority: str
    must_mirror: list[str]


class ReframingTarget(BaseModel):
    """A competency the writer should surface, anchored to real evidence."""

    model_config = _STRICT

    competency: str
    weight: float
    host_role_index: int
    real_evidence: list[str]
    framing_guidance: str
    no_evidence: bool


class GapTargets(BaseModel):
    """Top-level wrapper for the Gap Analyzer's structured output.

    ``messages.parse`` requires a single top-level model, so the list of
    reframing targets is wrapped here. The node unwraps ``targets`` back to a
    plain list before writing state.
    """

    model_config = _STRICT

    targets: list[ReframingTarget]


class RoleBullets(BaseModel):
    """Writer output for one role: bullets ONLY, keyed by role index.

    Deliberately carries no identity fields — integrity guarantee #1.
    """

    model_config = _STRICT

    index: int
    bullets: list[str]


class WriterOutput(BaseModel):
    """The writer's full output. Contains NO identity fields by construction."""

    model_config = _STRICT

    roles: list[RoleBullets]
    skills: list[str]
    summary: str


class PanelScore(BaseModel):
    """One recruiter persona's scores across the rubric dimensions.

    Scores are ints (0-100); range validation happens in application code.
    """

    model_config = _STRICT

    persona: str
    keyword_match: int
    impact_quality: int
    coherence: int
    plausibility: int
    formatting: int
    notes: str


class RevisionNotes(BaseModel):
    """Top-level wrapper for the Aggregator's distilled revision directives.

    ``messages.parse`` requires a single top-level model, so the ranked list of
    concrete directives is wrapped here (mirrors the ``GapTargets`` pattern).
    The aggregator node unwraps ``notes`` back to a plain list before writing
    state.
    """

    model_config = _STRICT

    notes: list[str]
