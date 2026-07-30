"""Project selector node - scores the hardcoded project vault against the JD.

Fires exactly once per pipeline run (positioned in the linear spine between
generate_skills and writer; back-edges re-enter at writer, skipping this node).

Selects exactly 2 projects: K1 (rank=1, 3 bullets) and K2 (rank=2, 2 bullets).
Bullet counts are enforced here, not by the LLM, so the selector prompt stays
simple (just ranking, no count specification).
"""
import json
import logging

from pydantic import BaseModel

from config.projects import PROJECTS
from src.pipeline.llm import parse_fast
from src.pipeline.schemas import JDVector, SelectedProject
from src.pipeline.state import PipelineState

log = logging.getLogger(__name__)

_STRICT = {"extra": "forbid"}

_SYSTEM = """You are a project relevance ranker.
Given a job description vector and a list of projects (each with an id and context),
rank the projects by relevance to the job and return the top 2 as a JSON array.
Output ONLY the JSON array with exactly 2 objects, each with keys: rank (1 or 2), id.
rank=1 is the most relevant. No explanation, no markdown fences."""


class _SelectorResult(BaseModel):
    rank: int
    id: str


class _SelectorOutput(BaseModel):
    selections: list[_SelectorResult]


def _build_selector_prompt(jd: JDVector, projects: list[dict]) -> str:
    jd_summary = (
        f"Seniority: {jd.seniority}\n"
        f"Must-mirror: {', '.join(jd.must_mirror)}\n"
        f"ATS keywords: {', '.join(jd.ats_keywords)}\n"
        f"Weighted skills: {', '.join(f'{s.name}({s.weight:.1f})' for s in jd.weighted_skills)}"
    )
    project_lines = "\n\n".join(
        f"id: {p['id']}\ncontext: {p['context']}" for p in projects
    )
    return f"## JOB DESCRIPTION\n{jd_summary}\n\n## PROJECTS\n{project_lines}"


def _assign_bullet_counts(selections: list[SelectedProject]) -> list[SelectedProject]:
    """Return new SelectedProject objects with bullet_count fixed by rank (immutable)."""
    counts = {1: 3, 2: 2}
    return [sp.model_copy(update={"bullet_count": counts.get(sp.rank, 2)}) for sp in selections]


def _llm_select(jd: JDVector, projects: list[dict]) -> list[SelectedProject]:
    """Call the fast LLM to rank projects and build SelectedProject objects."""
    user = _build_selector_prompt(jd, projects)
    result = parse_fast(_SYSTEM, user, _SelectorOutput)

    project_by_id = {p["id"]: p for p in projects}
    selected: list[SelectedProject] = []
    for item in result.selections[:2]:
        p = project_by_id.get(item.id)
        if p is None:
            log.warning("project_selector | unknown project id %r — skipping", item.id)
            continue
        selected.append(
            SelectedProject(
                rank=item.rank,
                id=item.id,
                context=p["context"],
                link=p["link"],
                bullet_count=0,  # overwritten by _assign_bullet_counts
            )
        )
    return _assign_bullet_counts(selected)


def project_select(state: PipelineState) -> dict:
    """Node: select top-2 projects from the vault, ranked against the JD."""
    jd = state["jd_vector"]
    log.info("project_select | scoring %d projects against JD…", len(PROJECTS))
    selected = _llm_select(jd, PROJECTS)
    for sp in selected:
        log.info(
            "project_select | rank=%d  id=%s  bullet_count=%d",
            sp.rank, sp.id, sp.bullet_count,
        )
    return {"selected_projects": selected}
