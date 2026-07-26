"""Writer agent - the Opus optimizer.

Assembles the user prompt from the extraction artifacts (``resume_struct``,
``jd_vector``, ``gap_targets``) and, on revision/compile bounces, the prior
``writer_output`` plus ``revision_notes`` / ``compile_errors``. Emits a
``WriterOutput`` (bullets + skills - no identity fields).

The user-message builder is a pure function so the deterministic "what does the
next draft see" behaviour is directly testable without any API call.
"""
import logging
import re

from config.settings import EFFORT_STRONG, MODEL_STRONG
from src.pipeline.llm import parse_strong

log = logging.getLogger(__name__)
from src.pipeline.schemas import WriterOutput
from src.pipeline.state import PipelineState
from src.prompts.writer import BULLET_SHAPES, SHAPE_NAMES, WRITER_SYSTEM

# The Writer prompt asks the model to self-verify length by appending a
# ``[chars: N]`` tag to each bullet. Those tags are a model-only scratchpad -
# they must be stripped before the length validator counts characters and
# before the renderer injects the bullet, or they leak into the final PDF.
_CHAR_ANNOTATION = re.compile(r"\s*\[chars:\s*\d+\]", re.IGNORECASE)


def strip_char_annotation(bullet: str) -> str:
    """Remove any ``[chars: N]`` self-verification tag(s) from a bullet."""
    return _CHAR_ANNOTATION.sub("", bullet).strip()


def sanitize_writer_output(output: WriterOutput) -> WriterOutput:
    """Return a WriterOutput with every ``[chars: N]`` tag stripped from bullets.

    Immutable: builds new objects. When no bullet actually changes, the original
    object is returned unchanged so object identity is preserved for callers.
    """
    changed = False
    cleaned_roles = []
    for role in output.roles:
        cleaned = [strip_char_annotation(b) for b in role.bullets]
        if cleaned != role.bullets:
            changed = True
            cleaned_roles.append(role.model_copy(update={"bullets": cleaned}))
        else:
            cleaned_roles.append(role)
    if not changed:
        return output
    return output.model_copy(update={"roles": cleaned_roles})


def render_revision_notes(revision_notes: list[str] | None) -> str:
    """Render the ranked revision directives into prompt text.

    The aggregator emits ``list[str]`` (ranked directives). A list is
    enumerated ("1. ..."), preserving the aggregator's ranking; an empty/None
    value renders "(none)".
    """
    if not revision_notes:
        return "(none)"
    directives = [str(note).strip() for note in revision_notes if str(note).strip()]
    if not directives:
        return "(none)"
    return "\n".join(f"{i}. {note}" for i, note in enumerate(directives, start=1))


def build_shape_directive(shapes: list[str] | None) -> str:
    """Compose the per-run bullet shape directive from BULLET_SHAPES.

    - ``None`` / ``[]`` / all four names → full rotation directive (semantically
      equivalent to the original hardcoded SHAPE ROTATION block).
    - one name → "USE ONLY {name} for every bullet. Do not rotate." + definition.
    - 2-3 names → "Rotate ONLY among: {…}." + selected definitions in canonical order.

    The function is pure and deterministic — the same input always gives the same string.
    """
    effective: set[str] = set(shapes) if shapes else set()

    # All four (or none) → full rotation directive rebuilt from catalog
    if not effective or effective >= set(SHAPE_NAMES):
        lines = [
            "SHAPE ROTATION (mandatory - not a menu):",
            "  Four bullet shapes exist. You MUST rotate them within each role - no two",
            "  consecutive bullets may use the same shape. Cycle through, don't default.",
            "",
        ]
        for name in SHAPE_NAMES:
            info = BULLET_SHAPES[name]
            lines.append(f"    {name} - {info['description']}")
        lines.append("")
        lines.append("  Example each, same underlying win, different shape:")
        for name in SHAPE_NAMES:
            info = BULLET_SHAPES[name]
            lines.append(f'    {name}: "{info["example"]}"')
        return "\n".join(lines)

    if len(effective) == 1:
        name = next(iter(effective))
        info = BULLET_SHAPES[name]
        return (
            f"USE ONLY {name} for every bullet. Do not rotate.\n\n"
            f"  {name} - {info['description']}\n"
            f'  Example: "{info["example"]}"'
        )

    # Subset (2 or 3 shapes) — output in canonical order
    ordered = [n for n in SHAPE_NAMES if n in effective]
    names_str = ", ".join(ordered)
    lines = [
        f"Rotate ONLY among: {names_str}. "
        "No two consecutive bullets in a role may share a shape.",
        "",
    ]
    for name in ordered:
        info = BULLET_SHAPES[name]
        lines.append(f"  {name} - {info['description']}")
        lines.append(f'  Example: "{info["example"]}"')
        lines.append("")
    return "\n".join(lines).rstrip()


def build_writer_user_message(state: PipelineState) -> str:
    """Assemble the Writer's user prompt from the current pipeline state.

    Always includes the core inputs (structured resume, JD vector, reframing
    targets). Conditionally appends:

    - the PROVEN EXAMPLES block (already labelled by the retrieval layer) when
      ``proven_examples`` is set;
    - a REVISION section (prior draft + ranked revision notes) when
      ``revision_notes`` is present or ``iteration`` >= 2;
    - a COMPILE ERRORS section when ``compile_errors`` is present (compile bounce).

    Pure and deterministic - the same state always yields the same string.
    """
    struct = state["resume_struct"]
    vector = state["jd_vector"]
    targets = state.get("gap_targets", [])
    targets_json = "[\n" + ",\n".join(
        t.model_dump_json(indent=2) for t in targets
    ) + "\n]" if targets else "[]"

    shape_directive = build_shape_directive(state.get("bullet_shapes"))

    sections = [
        "## BULLET SHAPE DIRECTIVE",
        shape_directive,
        "",
        "## RESUME (structured - the ONLY ground truth for every claim)",
        struct.model_dump_json(indent=2),
        "",
        "## JOB DESCRIPTION (vector - mirror this vocabulary only where truthful)",
        vector.model_dump_json(indent=2),
        "",
        "## REFRAMING TARGETS (apply each framing_guidance to its host_role_index)",
        targets_json,
    ]

    proven_examples = state.get("proven_examples")
    if proven_examples:
        sections += ["", proven_examples]

    revision_notes = state.get("revision_notes")
    if revision_notes or state.get("iteration", 1) >= 2:
        prior = state.get("writer_output")
        sections += [
            "",
            "## PRIOR DRAFT (preserve bullets that already scored well)",
            prior.model_dump_json(indent=2) if prior is not None else "(none)",
            "",
            "## REVISION NOTES (ranked - address highest-priority items first)",
            render_revision_notes(revision_notes),
        ]

    identity_violations = state.get("identity_violations")
    if identity_violations:
        violations_text = "\n".join(f"- {v}" for v in identity_violations)
        sections += [
            "",
            "## IDENTITY VIOLATIONS (DO NOT change these identity fields - they are locked)",
            violations_text,
        ]

    length_violations = state.get("length_violations")
    if length_violations:
        violations_text = "\n".join(length_violations)
        sections += [
            "",
            "## LENGTH VIOLATIONS (fix ONLY these bullets to 195-210 chars, keep the rest)",
            violations_text,
        ]

    compile_errors = state.get("compile_errors")
    if compile_errors:
        sections += [
            "",
            "## COMPILE ERRORS (compile retry - fix ONLY the LaTeX-affecting content)",
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
        "→ sending to %s (effort=%s)",
        iteration,
        "yes" if has_revision else "no",
        "yes" if has_compile_err else "no",
        MODEL_STRONG,
        EFFORT_STRONG,
    )
    user_msg = build_writer_user_message(state)
    output = parse_strong(WRITER_SYSTEM, user_msg, WriterOutput)
    # Strip the model's [chars: N] self-verification tags before anything
    # downstream sees them - the validator must count clean bullets and the
    # renderer must never leak the tags into the PDF.
    output = sanitize_writer_output(output)
    total_bullets = sum(len(r.bullets) for r in output.roles)
    log.info(
        "writer       | done - %d roles, %d total bullets",
        len(output.roles), total_bullets,
    )
    return {"writer_output": output}
