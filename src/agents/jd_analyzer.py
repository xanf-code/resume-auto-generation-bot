"""JD Analyzer agent — raw job description -> JDVector.

A cheap, fast (Haiku) pass that turns the target JD into the requirement vector
the Writer optimizes against: weighted skills, literal ATS keywords, seniority,
and the top must-mirror phrases.
"""
from src.pipeline.llm import parse_fast
from src.pipeline.schemas import JDVector
from src.pipeline.state import PipelineState
from src.prompts.extraction import JD_SYSTEM


def analyze_jd(state: PipelineState) -> dict:
    """Node: analyze the raw JD into a JDVector.

    Reads ``jd_raw``; returns a NEW dict with ``jd_vector`` (never mutates the
    incoming state).
    """
    jd_raw = state["jd_raw"]
    vector = parse_fast(JD_SYSTEM, jd_raw, JDVector)
    return {"jd_vector": vector}
