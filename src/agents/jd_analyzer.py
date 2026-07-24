"""JD Analyzer agent — raw job description -> JDVector.

A cheap, fast (Haiku) pass that turns the target JD into the requirement vector
the Writer optimizes against: weighted skills, literal ATS keywords, seniority,
and the top must-mirror phrases.
"""
import logging

from config.settings import MODEL_FAST
from src.pipeline.llm import parse_fast
from src.pipeline.schemas import JDVector
from src.pipeline.state import PipelineState
from src.prompts.extraction import JD_SYSTEM

log = logging.getLogger(__name__)


def analyze_jd(state: PipelineState) -> dict:
    """Node: analyze the raw JD into a JDVector."""
    jd_raw = state["jd_raw"]
    log.info("analyze_jd  | sending %d chars to %s", len(jd_raw), MODEL_FAST)
    vector = parse_fast(JD_SYSTEM, jd_raw, JDVector)
    log.info(
        "analyze_jd  | done — %d weighted skills, %d ATS keywords, "
        "%d must-mirror, seniority=%r",
        len(vector.weighted_skills),
        len(vector.ats_keywords),
        len(vector.must_mirror),
        vector.seniority,
    )
    log.info(
        "analyze_jd  | ATS keywords (%d): %s",
        len(vector.ats_keywords),
        ", ".join(vector.ats_keywords),
    )
    log.info(
        "analyze_jd  | weighted skills (%d): %s",
        len(vector.weighted_skills),
        ", ".join(f"{s.name}({s.weight:.2f})" for s in vector.weighted_skills),
    )
    log.info(
        "analyze_jd  | must-mirror phrases (%d): %s",
        len(vector.must_mirror),
        " | ".join(vector.must_mirror),
    )
    return {"jd_vector": vector}
