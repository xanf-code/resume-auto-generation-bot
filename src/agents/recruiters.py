"""Recruiter panel - four adversarial Opus personas, scored concurrently.

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

import openai

from src.pipeline.llm import effective_scoring, parse_scoring

log = logging.getLogger(__name__)
from src.pipeline.schemas import InventedTool, JDVector, PanelScore, ResumeStruct
from src.pipeline.state import PipelineState
from src.prompts.jd_tagger import envelope_for
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
    invented_stack: list[InventedTool] | None = None,
    fabrication_envelope: tuple[str, ...] | None = None,
) -> str:
    """Assemble one persona's user prompt.

    Always includes the rendered LaTeX and the JD vector. Includes the
    structured source resume (``source_evidence``), the writer's fabrication
    ledger (``invented_stack``), and the ``## FABRICATION ENVELOPE`` (the same
    legal fabrication vocabulary the Writer was given) ONLY when provided -
    that is, for the Skeptic, so it scores plausibility against the identical
    envelope rather than its own judgment call. Pure and deterministic.
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
            "## SOURCE RESUME (structured - source_evidence is the ONLY ground "
            "truth for every claim)",
            struct.model_dump_json(indent=2),
        ]
    if invented_stack is not None:
        stack_json = (
            "[\n" + ",\n".join(t.model_dump_json(indent=2) for t in invented_stack) + "\n]"
            if invented_stack
            else "[]"
        )
        sections += [
            "",
            "## INVENTED STACK (writer's fabrication ledger - assess cross-bullet "
            "coherence, not just per-line plausibility)",
            stack_json,
        ]
    if fabrication_envelope is not None:
        envelope_text = (
            "\n".join(f"- {tool}" for tool in fabrication_envelope)
            if fabrication_envelope
            else "(none - no tagged domains this run; the writer had nothing "
            "beyond the source material to invent)"
        )
        sections += [
            "",
            "## FABRICATION ENVELOPE (the ONLY legal fabrication vocabulary the "
            "writer was given - score claims outside it as unsupported)",
            envelope_text,
        ]
    return "\n".join(sections) + "\n"


# gpt-4o-mini occasionally rambles past its completion cap instead of emitting
# the (tiny) PanelScore schema - a known repetition failure mode, not a real
# evaluation. One retry usually clears it; a second miss falls back to this
# neutral placeholder (below THRESHOLD so a broken score can't wrongly pass the
# panel, but above PLAUSIBILITY_FLOOR so it can't wrongly veto one either)
# rather than crashing the whole run.
_FALLBACK_SCORE_VALUE = 50
_LENGTH_LIMIT_NOTE = (
    "Scoring call exceeded the model's output length limit twice; this is a "
    "neutral placeholder score, not a real evaluation."
)


async def score_one(persona_name: str, system: str, user: str) -> PanelScore:
    """Score one persona, running the sync ``parse_scoring`` off the event loop.

    Offloaded via ``asyncio.to_thread`` so a ``gather`` over the four personas
    executes their scoring model calls concurrently rather than serially.

    The ``persona`` field is OVERRIDDEN with the canonical ``persona_name`` after
    the call - the model may return a paraphrase, but the display/aggregator rely
    on exact string matching against ``PERSONAS`` keys.
    """
    try:
        score = await asyncio.to_thread(parse_scoring, system, user, PanelScore)
    except openai.LengthFinishReasonError:
        log.warning(
            "recruiter    | %-22s hit the output length cap - retrying once",
            persona_name,
        )
        try:
            score = await asyncio.to_thread(parse_scoring, system, user, PanelScore)
        except openai.LengthFinishReasonError:
            log.error(
                "recruiter    | %-22s hit the output length cap twice - "
                "falling back to a neutral placeholder score",
                persona_name,
            )
            return PanelScore(
                persona=persona_name,
                keyword_match=_FALLBACK_SCORE_VALUE,
                impact_quality=_FALLBACK_SCORE_VALUE,
                coherence=_FALLBACK_SCORE_VALUE,
                plausibility=_FALLBACK_SCORE_VALUE,
                formatting=_FALLBACK_SCORE_VALUE,
                notes=_LENGTH_LIMIT_NOTE,
            )
    return score.model_copy(update={"persona": persona_name})


async def run_panel(state: PipelineState) -> list[PanelScore]:
    """Build each persona's message and score all four concurrently."""
    latex_rendered = state["latex_rendered"]
    vector = state["jd_vector"]
    struct = state["resume_struct"]
    invented_stack = state.get("invented_stack") or getattr(
        state.get("writer_output"), "invented_stack", []
    )
    fabrication_envelope = envelope_for(state.get("jd_domains") or [])

    tasks = []
    for persona_name, (system, needs_source) in PERSONAS.items():
        user = build_user_message(
            latex_rendered,
            vector,
            struct if needs_source else None,
            invented_stack if needs_source else None,
            fabrication_envelope if needs_source else None,
        )
        tasks.append(score_one(persona_name, system, user))

    return list(await asyncio.gather(*tasks))


def recruiter_panel(state: PipelineState) -> dict:
    """Node: run the four-persona panel and return their scores.

    Exact-match memoized on ``latex_rendered``: when the current draft is
    byte-identical to the one scored last (``panel_cache_latex``) - which
    happens when the writer plateaus and re-emits the same content across
    revision iterations - the panel is skipped entirely and the cached scores
    are reused instead of re-running all four persona calls.
    """
    latex_rendered = state["latex_rendered"]
    cached_latex = state.get("panel_cache_latex")
    cached_scores = state.get("panel_cache_scores")
    if cached_latex == latex_rendered and cached_scores is not None:
        log.info("recruiter    | latex unchanged since last scoring - reusing cached panel scores")
        return {"panel_scores": cached_scores, "panel_cache_latex": cached_latex, "panel_cache_scores": cached_scores}

    role = effective_scoring()
    log.info(
        "recruiter    | spawning 4 %s personas concurrently… (effort=%s, temp=%s)",
        role.model, role.effort, role.temperature,
    )
    scores = asyncio.run(run_panel(state))
    for s in scores:
        log.info(
            "recruiter    | %-22s km=%3d iq=%3d coh=%3d plaus=%3d fmt=%3d",
            s.persona, s.keyword_match, s.impact_quality,
            s.coherence, s.plausibility, s.formatting,
        )
    return {"panel_scores": scores, "panel_cache_latex": latex_rendered, "panel_cache_scores": scores}
