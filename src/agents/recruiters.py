"""Recruiter panel — four adversarial Opus personas, scored concurrently.

Each persona reviews the SAME rendered resume through a distinct lens and
returns a ``PanelScore`` via ``parse_strong(..., PanelScore)``. Three personas
(ATS Matcher, Hiring Manager, Technical Screener) see the rendered LaTeX plus
the JD vector; the Skeptic ALSO sees the structured source resume so it can
check every claim against ``source_evidence``.

The four calls run truly concurrently: ``parse_strong`` is synchronous, so each
call is offloaded to a worker thread via ``asyncio.to_thread`` and awaited
together with ``asyncio.gather``.
"""
import asyncio
import logging

from src.pipeline.llm import parse_strong

log = logging.getLogger(__name__)
from src.pipeline.schemas import JDVector, PanelScore, ResumeStruct
from src.pipeline.state import PipelineState
from src.prompts.recruiters import (
    ATS_MATCHER_SYSTEM,
    HIRING_MANAGER_SYSTEM,
    SKEPTIC_SYSTEM,
    TECH_SCREENER_SYSTEM,
)

# persona name -> (system prompt, needs_source_struct)
# Only the Skeptic needs the structured source resume (source_evidence).
PERSONAS: dict[str, tuple[str, bool]] = {
    "ATS Matcher": (ATS_MATCHER_SYSTEM, False),
    "Hiring Manager": (HIRING_MANAGER_SYSTEM, False),
    "Technical Screener": (TECH_SCREENER_SYSTEM, False),
    "Skeptic": (SKEPTIC_SYSTEM, True),
}


def build_user_message(
    latex_rendered: str,
    vector: JDVector,
    struct: ResumeStruct | None,
) -> str:
    """Assemble one persona's user prompt.

    Always includes the rendered LaTeX and the JD vector. Includes the
    structured source resume (``source_evidence``) ONLY when ``struct`` is
    provided — that is, for the Skeptic. Pure and deterministic.
    """
    sections = [
        "## RENDERED RESUME (LaTeX)",
        latex_rendered,
        "",
        "## JOB DESCRIPTION (vector)",
        vector.model_dump_json(indent=2),
    ]
    if struct is not None:
        sections += [
            "",
            "## SOURCE RESUME (structured — source_evidence is the ONLY ground "
            "truth for every claim)",
            struct.model_dump_json(indent=2),
        ]
    return "\n".join(sections) + "\n"


async def score_one(persona_name: str, system: str, user: str) -> PanelScore:
    """Score one persona, running the sync ``parse_strong`` off the event loop.

    Offloaded via ``asyncio.to_thread`` so a ``gather`` over the four personas
    executes their Opus calls concurrently rather than serially.

    The ``persona`` field is OVERRIDDEN with the canonical ``persona_name`` after
    the call — the model may return a paraphrase, but the display/aggregator rely
    on exact string matching against ``PERSONAS`` keys.
    """
    score = await asyncio.to_thread(parse_strong, system, user, PanelScore)
    return score.model_copy(update={"persona": persona_name})


async def run_panel(state: PipelineState) -> list[PanelScore]:
    """Build each persona's message and score all four concurrently."""
    latex_rendered = state["latex_rendered"]
    vector = state["jd_vector"]
    struct = state["resume_struct"]

    tasks = []
    for persona_name, (system, needs_source) in PERSONAS.items():
        user = build_user_message(
            latex_rendered, vector, struct if needs_source else None
        )
        tasks.append(score_one(persona_name, system, user))

    return list(await asyncio.gather(*tasks))


def recruiter_panel(state: PipelineState) -> dict:
    """Node: run the four-persona panel and return their scores."""
    log.info("recruiter    | spawning 4 Opus personas concurrently…")
    scores = asyncio.run(run_panel(state))
    for s in scores:
        log.info(
            "recruiter    | %-22s km=%3d iq=%3d coh=%3d plaus=%3d fmt=%3d",
            s.persona, s.keyword_match, s.impact_quality,
            s.coherence, s.plausibility, s.formatting,
        )
    return {"panel_scores": scores}
