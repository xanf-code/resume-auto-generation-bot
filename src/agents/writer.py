"""Writer agent — the Opus optimizer.

Assembles the user prompt from the extraction artifacts (``resume_struct``,
``jd_vector``, ``gap_targets``) and, on revision/compile bounces, the prior
``writer_output`` plus ``revision_notes`` / ``compile_errors``. Emits a
``WriterOutput`` (bullets + skills + summary — no identity fields).

The user-message builder is a pure function so the deterministic "what does the
next draft see" behaviour is directly testable without any API call.
"""
import logging

from src.pipeline.llm import parse_strong

log = logging.getLogger(__name__)
from src.pipeline.schemas import WriterOutput
from src.pipeline.state import PipelineState
from src.prompts.writer import WRITER_SYSTEM


def render_revision_notes(revision_notes: object) -> str:
    """Render the revision directives into prompt text.

    The aggregator emits ``list[str]`` (ranked directives); a legacy lone
    ``str`` is also accepted so callers can pass either shape. A list is
    enumerated ("1. ..."), preserving the aggregator's ranking; an empty/None
    value renders "(none)".
    """
    if revision_notes is None:
        return "(none)"
    if isinstance(revision_notes, str):
        return revision_notes or "(none)"
    directives = [str(note).strip() for note in revision_notes if str(note).strip()]
    if not directives:
        return "(none)"
    return "\n".join(f"{i}. {note}" for i, note in enumerate(directives, start=1))


def build_writer_user_message(state: PipelineState) -> str:
    """Assemble the Writer's user prompt from the current pipeline state.

    Always includes the core inputs (structured resume, JD vector, reframing
    targets). Conditionally appends:

    - a REVISION section (prior draft + ranked revision notes) when
      ``revision_notes`` is present or ``iteration`` >= 2;
    - a COMPILE ERRORS section when ``compile_errors`` is present (compile bounce).

    Pure and deterministic — the same state always yields the same string.
    """
    struct = state["resume_struct"]
    vector = state["jd_vector"]
    targets = state.get("gap_targets", [])
    targets_json = "[\n" + ",\n".join(
        t.model_dump_json(indent=2) for t in targets
    ) + "\n]" if targets else "[]"

    sections = [
        "## RESUME (structured — the ONLY ground truth for every claim)",
        struct.model_dump_json(indent=2),
        "",
        "## JOB DESCRIPTION (vector — mirror this vocabulary only where truthful)",
        vector.model_dump_json(indent=2),
        "",
        "## REFRAMING TARGETS (apply each framing_guidance to its host_role_index)",
        targets_json,
    ]

    revision_notes = state.get("revision_notes")
    if revision_notes or state.get("iteration", 1) >= 2:
        prior = state.get("writer_output")
        sections += [
            "",
            "## PRIOR DRAFT (preserve bullets that already scored well)",
            prior.model_dump_json(indent=2) if prior is not None else "(none)",
            "",
            "## REVISION NOTES (ranked — address highest-priority items first)",
            render_revision_notes(revision_notes),
        ]

    compile_errors = state.get("compile_errors")
    if compile_errors:
        sections += [
            "",
            "## COMPILE ERRORS (compile retry — fix ONLY the LaTeX-affecting content)",
            compile_errors,
        ]

    return "\n".join(sections) + "\n"


def write_resume(state: PipelineState) -> dict:
    """Node: generate the tailored ``WriterOutput`` from the current state."""
    iteration = state.get("iteration", 1)
    has_revision = bool(state.get("revision_notes"))
    has_compile_err = bool(state.get("compile_errors"))
    log.info(
        "writer       | iteration=%d  revision_notes=%s  compile_errors=%s  "
        "→ sending to Opus (effort=high)",
        iteration,
        "yes" if has_revision else "no",
        "yes" if has_compile_err else "no",
    )
    user_msg = build_writer_user_message(state)
    output = parse_strong(WRITER_SYSTEM, user_msg, WriterOutput, effort="high")
    total_bullets = sum(len(r.bullets) for r in output.roles)
    log.info(
        "writer       | done — %d roles, %d total bullets, %d skills, "
        "summary=%d chars",
        len(output.roles), total_bullets, len(output.skills), len(output.summary),
    )
    return {"writer_output": output}
