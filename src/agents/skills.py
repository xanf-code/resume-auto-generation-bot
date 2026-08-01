"""Skills agent - one-shot categorized skill dump generator.

Runs exactly once per pipeline run, between gap_analysis and writer, using
MODEL_SKILLS (gpt-4o-mini). Skills are stable across every revision iteration
because this node fires before the writer loop and the graph's back-edges never
re-enter before it.

Failure is graceful: on any exception the node emits an empty SkillDump and
lets the run finish (PDF + score still ship).
"""
import logging

from src.pipeline.llm import effective_skills, parse_skills
from src.pipeline.schemas import JDVector, ReframingTarget, ResumeStruct, SkillDump
from src.pipeline.state import PipelineState
from src.prompts.skills import SKILLS_SYSTEM

log = logging.getLogger(__name__)


def build_skills_user_message(
    struct: ResumeStruct,
    vector: JDVector,
    gap_targets: list[ReframingTarget],
) -> str:
    """Assemble the user prompt for the skill dump call (pure)."""
    active_competencies = [t.competency for t in gap_targets if not t.no_evidence]
    competencies_text = (
        "\n".join(f"- {c}" for c in active_competencies)
        if active_competencies
        else "(none)"
    )
    return (
        "## RESUME SKILLS (declared in the source resume)\n"
        + "\n".join(f"- {s}" for s in struct.skills)
        + "\n\n"
        "## JOB DESCRIPTION (vector - draw vocabulary from here)\n"
        + vector.model_dump_json(indent=2)
        + "\n\n"
        "## GAP-REFRAME COMPETENCIES (skills with real evidence being surfaced)\n"
        + competencies_text
        + "\n"
    )


def generate_skills(state: PipelineState) -> dict:
    """Node: generate the categorized SkillDump exactly once.

    Idempotency guard: if skill_dump is already a SkillDump instance, return {}
    so LangGraph leaves the existing value untouched. Structurally this node
    fires once (before the writer loop) but the guard is belt-and-suspenders.
    """
    if isinstance(state.get("skill_dump"), SkillDump):
        return {}

    struct = state["resume_struct"]
    vector = state["jd_vector"]
    targets = state.get("gap_targets", [])

    role = effective_skills()
    log.info(
        "skills       | generating skill dump → %s (effort=%s, params=%s)",
        role.model, role.effort, role.extra_params,
    )
    try:
        msg = build_skills_user_message(struct, vector, targets)
        dump = parse_skills(SKILLS_SYSTEM, msg, SkillDump)
        log.info("skills       | done - %d skills across 4 buckets", dump.total())
        return {"skill_dump": dump}
    except Exception as exc:
        log.warning("skills       | call failed (%s) - emitting empty dump", exc)
        return {"skill_dump": SkillDump()}
