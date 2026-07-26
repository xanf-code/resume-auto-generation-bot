"""JD Tagger agent - raw job description -> controlled-vocabulary jd_type tags.

A cheap, fast (Haiku) pass that classifies the JD into 1-3 tags from
``JD_TYPE_VOCAB``. Tags drive "similar role" retrieval matching (tag overlap,
no embeddings needed at this volume) and tuning segmentation, and are recorded
on every note. Reuses the existing fast-model plumbing - no new infrastructure.
"""
import logging

from src.pipeline.llm import parse_fast
from src.pipeline.schemas import JDTags
from src.prompts.jd_tagger import JD_TAGGER_SYSTEM, JD_TYPE_VOCAB

log = logging.getLogger(__name__)


def classify_jd_type(jd_raw: str) -> list[str]:
    """Classify a raw JD into a deduped, in-vocabulary list of jd_type tags.

    Never fails the run: any error from the model (or an entirely out-of-vocab
    response) yields an empty list rather than propagating.
    """
    try:
        result = parse_fast(JD_TAGGER_SYSTEM, jd_raw, JDTags)
    except Exception as exc:
        log.warning("jd_tagger    | call failed (%s) - emitting no tags", exc)
        return []

    seen: set[str] = set()
    tags: list[str] = []
    for tag in result.tags:
        if tag in JD_TYPE_VOCAB and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags
