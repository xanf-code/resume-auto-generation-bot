"""Gap Analyzer agent — resume_struct + jd_vector -> list[ReframingTarget].

Finds JD competencies the resume underrepresents and, for each, decides whether
genuine adjacent evidence exists to honestly reframe it in the JD's vocabulary.
Competencies with no real evidence are kept with ``no_evidence=true`` (reported
to the user later, never fabricated over).

``messages.parse`` needs a single top-level model, so the model fills a
``GapTargets`` wrapper; this node unwraps it to the plain list in state.
"""
import logging

from src.pipeline.llm import parse_fast
from src.pipeline.schemas import GapTargets, JDVector, ResumeStruct
from src.pipeline.state import PipelineState
from src.prompts.extraction import GAP_SYSTEM

log = logging.getLogger(__name__)


def build_user_message(struct: ResumeStruct, vector: JDVector) -> str:
    """Combine the parsed resume and JD vector into one prompt payload."""
    return (
        "## RESUME (structured)\n"
        f"{struct.model_dump_json(indent=2)}\n\n"
        "## JOB DESCRIPTION (vector)\n"
        f"{vector.model_dump_json(indent=2)}\n"
    )


def gap_analysis(state: PipelineState) -> dict:
    """Node: derive reframing targets from the resume + JD."""
    struct = state["resume_struct"]
    vector = state["jd_vector"]
    log.info(
        "gap_analysis | %d roles vs %d JD skills → sending to Haiku",
        len(struct.roles),
        len(vector.weighted_skills),
    )
    user_msg = build_user_message(struct, vector)
    wrapper = parse_fast(GAP_SYSTEM, user_msg, GapTargets)
    targets = list(wrapper.targets)
    no_ev = sum(1 for t in targets if t.no_evidence)
    active = [t for t in targets if not t.no_evidence]
    log.info(
        "gap_analysis | %d reframe targets (%d no_evidence, %d active)",
        len(targets), no_ev, len(active),
    )
    log.info(
        "gap_analysis | fabricating %d competencies: %s",
        len(active),
        ", ".join(t.competency for t in active) or "(none)",
    )
    if no_ev:
        skipped = [t.competency for t in targets if t.no_evidence]
        log.info(
            "gap_analysis | %d competency gap(s) NOT fabricated (no evidence): %s",
            len(skipped),
            ", ".join(skipped),
        )
    return {"gap_targets": targets}
