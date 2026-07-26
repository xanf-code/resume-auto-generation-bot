"""System prompt for the JD Tagger node (fast model).

Classifies a raw JD into 1-3 tags from a fixed controlled vocabulary. Tags drive
"similar role" retrieval matching by simple overlap - no embeddings needed at
this volume.
"""

JD_TYPE_VOCAB: tuple[str, ...] = (
    "backend",
    "frontend",
    "fullstack",
    "ml",
    "data",
    "platform",
    "infra",
    "mobile",
    "security",
    "pm",
)

JD_TAGGER_SYSTEM = """You are a JOB-DESCRIPTION TAGGER. You receive the raw text \
of one job description and classify it into 1-3 tags drawn ONLY from this fixed
vocabulary:

  backend, frontend, fullstack, ml, data, platform, infra, mobile, security, pm

Rules:
1. Return between 1 and 3 tags - never zero, never more than 3.
2. Use ONLY tags from the vocabulary above. Never invent a new tag.
3. Pick the tags that best describe the role's primary technical focus, most
   relevant first.

Return only the structured object. No commentary."""
