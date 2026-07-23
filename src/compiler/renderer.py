"""Deterministic LaTeX renderer — integrity guarantee #1 (structural).

Identity fields (name, contact, company, title, start, end) are sourced
*exclusively* from the ``IdentityLedger``. Bullets, skills, and the summary are
sourced *exclusively* from the ``WriterOutput``. The writer's output can never
reach an identity slot: the template only receives ledger values in identity
positions, and writer values in content positions.

Every injected string is LaTeX-escaped (backslash first) before templating.
The renderer owns the Jinja2 ``Environment`` configuration, remapping the
delimiters to ``\\VAR{ }`` / ``\\BLOCK{ }`` so they never collide with LaTeX
braces.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from src.pipeline.schemas import IdentityLedger, WriterOutput

# Directory holding ``resume.tex.j2``.
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_TEMPLATE_NAME = "resume.tex.j2"

# Marker emitted as a LaTeX comment before each experience role header. The
# identity check counts these markers to detect smuggled-in extra roles.
ROLE_HEADER_MARKER = "%% ROLE-HEADER %%"

# Placeholder rendered when there is no education content, keeping the template
# output valid and terminal-authentic rather than an empty section.
_NO_EDUCATION_PLACEHOLDER = "See attached transcript."

# LaTeX special character → replacement map. Applied in a SINGLE left-to-right
# pass (character by character) so replacement sequences that themselves
# contain braces (e.g. ``\textbackslash{}``) are never re-escaped. Backslash is
# handled here like any other character; the single-pass guarantee removes the
# ordering hazard that a multi-``replace`` approach would have.
_LATEX_ESCAPE_MAP: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "$": r"\$",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(s: str) -> str:
    """Escape LaTeX special characters in ``s``.

    Handles ``& % # _ $ { } ~ ^ \\``. Implemented as a single character-by-
    character pass so the braces introduced by replacements (like
    ``\\textbackslash{}``) are never re-escaped — this is the "backslash first"
    correctness guarantee expressed structurally rather than by ordering.
    """
    return "".join(_LATEX_ESCAPE_MAP.get(ch, ch) for ch in s)


def _build_environment() -> Environment:
    """Create the LaTeX-aware Jinja2 environment (delimiters remapped)."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )


def _escaped_experience(
    ledger: IdentityLedger, writer_output: WriterOutput
) -> list[dict[str, object]]:
    """Zip ledger roles with writer bullets, escaping every string.

    Identity fields come ONLY from ``ledger``; bullets come ONLY from
    ``writer_output``, matched to the role by ``RoleBullets.index``.
    """
    bullets_by_index: dict[int, list[str]] = {
        rb.index: list(rb.bullets) for rb in writer_output.roles
    }
    experience: list[dict[str, object]] = []
    for idx, role in enumerate(ledger.roles):
        raw_bullets = bullets_by_index.get(idx, [])
        experience.append(
            {
                "company": latex_escape(role.company),
                "title": latex_escape(role.title),
                "start": latex_escape(role.start),
                "end": latex_escape(role.end),
                "bullets": [latex_escape(b) for b in raw_bullets],
            }
        )
    return experience


def render(identity_ledger: IdentityLedger, writer_output: WriterOutput) -> str:
    """Render the resume LaTeX from a locked ledger + writer output.

    Args:
        identity_ledger: The immutable source of truth for identity fields.
        writer_output: The writer's bullets/skills/summary — never identity.

    Returns:
        The rendered LaTeX document as a string.
    """
    env = _build_environment()
    template = env.get_template(_TEMPLATE_NAME)

    context = {
        # Identity slots — ledger ONLY.
        "name": latex_escape(identity_ledger.name),
        "contact": latex_escape(identity_ledger.contact),
        "experience": _escaped_experience(identity_ledger, writer_output),
        # Content slots — writer ONLY.
        "summary": latex_escape(writer_output.summary),
        "skills": [latex_escape(s) for s in writer_output.skills],
        # Education is not part of the writer/ledger split in Phase 3; render a
        # deterministic placeholder so the section is well-formed.
        "education": [],
        "no_education_placeholder": _NO_EDUCATION_PLACEHOLDER,
        # Structural marker — a valid LaTeX comment (starts with %) emitted
        # verbatim before each role header so the identity check can count
        # roles independently of any escaping.
        "role_header_marker": ROLE_HEADER_MARKER,
    }

    return template.render(**context)
