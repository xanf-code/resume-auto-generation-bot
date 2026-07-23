"""Gap Analyzer agent — resume_struct + jd_vector -> list[ReframingTarget].

Finds JD competencies the resume underrepresents and, for each, decides whether
genuine adjacent evidence exists to honestly reframe it in the JD's vocabulary.
Competencies with no real evidence are kept with ``no_evidence=true`` (reported
to the user later, never fabricated over).

``messages.parse`` needs a single top-level model, so the model fills a
``GapTargets`` wrapper; this node unwraps it to the plain list in state.
"""
from src.pipeline.llm import parse_fast
from src.pipeline.schemas import GapTargets, JDVector, ResumeStruct
from src.pipeline.state import PipelineState
from src.prompts.extraction import GAP_SYSTEM


def build_user_message(struct: ResumeStruct, vector: JDVector) -> str:
    """Combine the parsed resume and JD vector into one prompt payload."""
    return (
        "## RESUME (structured)\n"
        f"{struct.model_dump_json(indent=2)}\n\n"
        "## JOB DESCRIPTION (vector)\n"
        f"{vector.model_dump_json(indent=2)}\n"
    )


def gap_analysis(state: PipelineState) -> dict:
    """Node: derive reframing targets from the resume + JD.

    Reads ``resume_struct`` and ``jd_vector``; returns a NEW dict with
    ``gap_targets`` as a plain list of ReframingTarget (never mutates state).
    """
    struct = state["resume_struct"]
    vector = state["jd_vector"]
    user_msg = build_user_message(struct, vector)
    wrapper = parse_fast(GAP_SYSTEM, user_msg, GapTargets)
    return {"gap_targets": list(wrapper.targets)}
