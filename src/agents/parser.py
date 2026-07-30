"""Parser agent - raw resume .tex -> ResumeStruct + derived IdentityLedger.

The parser LLM extracts the structured resume; this node then DERIVES the
immutable identity ledger from it and runs a defensive guard that every
identity string (company / title / start / end) still appears verbatim in the
source .tex. Any drift means the model paraphrased an identity field, which the
guard rejects loudly.
"""
import logging
import re

from config.settings import MODEL_FAST
from src.pipeline.llm import parse_fast

log = logging.getLogger(__name__)
from src.pipeline.schemas import IdentityLedger, ResumeStruct, Role
from src.pipeline.state import PipelineState
from src.prompts.extraction import PARSER_SYSTEM

_IDENTITY_FIELDS = ("company", "title", "start", "end")

# A LaTeX command wrapper like \textbf{Jane Doe} -> "Jane Doe", capturing the
# command name too so callers can skip structural commands.
_TEX_COMMAND_NAMED = re.compile(r"\\([a-zA-Z]+)\*?\{([^{}]*)\}")
# A plausible email address.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Lines that can only be preamble - dropped before name extraction when there
# is no explicit ``\begin{document}`` to slice on.
_PREAMBLE_LINE_PREFIXES = (
    "\\documentclass", "\\usepackage", "\\RequirePackage", "\\newcommand",
    "\\renewcommand", "\\providecommand", "\\setmainfont", "\\setsansfont",
    "\\newfontfamily", "\\definecolor", "\\geometry", "\\pagestyle",
    "\\setlength", "\\input", "\\include", "\\DeclareUnicodeCharacter",
)

# Command names whose braced argument is NEVER a person's name - structural,
# environment, or resource commands. Their captured arg (e.g. "center" from
# ``\begin{center}``, "XCharter" from ``\usepackage{XCharter}``) is skipped.
_STRUCTURAL_CMDS = frozenset({
    "begin", "end", "section", "subsection", "subsubsection",
    "vspace", "hspace", "textcolor", "definecolor", "color",
    "includegraphics", "label", "ref", "href", "url", "item",
    "usepackage", "documentclass", "requirepackage", "setmainfont",
    "setsansfont", "newfontfamily", "newcommand", "renewcommand",
    "providecommand", "hfill", "par", "centering", "raggedright",
})

_DOCUMENT_MARKER = "\\begin{document}"


def _looks_like_name(value: str) -> bool:
    """Heuristic: a name has letters and is not an email/URL/nested command."""
    v = value.strip()
    if not v or "@" in v or "\\" in v or "http" in v.lower():
        return False
    return any(ch.isalpha() for ch in v)


def _document_body(resume_tex_raw: str) -> str:
    """Return the content the name can live in - never the preamble.

    Prefer everything after ``\\begin{document}``. When the source has no
    document environment, drop lines that can only be preamble commands
    (``\\usepackage{...}`` etc.) so a font/package argument can't masquerade as
    the candidate name.
    """
    idx = resume_tex_raw.find(_DOCUMENT_MARKER)
    if idx != -1:
        return resume_tex_raw[idx + len(_DOCUMENT_MARKER):]
    kept = [
        line
        for line in resume_tex_raw.splitlines()
        if not line.lstrip().startswith(_PREAMBLE_LINE_PREFIXES)
    ]
    return "\n".join(kept)


def extract_name(resume_tex_raw: str) -> str:
    """Best-effort candidate name from the raw .tex.

    Convention: the name is the first formatting-command content in the DOCUMENT
    BODY (e.g. ``\\textbf{Jane Doe}``) - never a preamble/font argument and never
    a structural command like ``\\begin{center}``. Falls back to the first
    non-empty content line that reads like a name.
    """
    body = _document_body(resume_tex_raw)
    for match in _TEX_COMMAND_NAMED.finditer(body):
        cmd, arg = match.group(1).lower(), match.group(2).strip()
        if cmd in _STRUCTURAL_CMDS:
            continue
        if _looks_like_name(arg):
            return arg
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("\\") and _looks_like_name(stripped):
            return stripped
    return ""


def extract_contact(resume_tex_raw: str) -> str:
    """Best-effort contact string from the raw .tex (email preferred)."""
    match = _EMAIL.search(resume_tex_raw)
    return match.group(0) if match else ""


def derive_ledger(
    struct: ResumeStruct, name: str, contact: str
) -> IdentityLedger:
    """Build the immutable ledger from a parsed struct + name/contact.

    Identity fields are copied character-exact from each ResumeRole - this is
    the single source of truth the renderer later injects.
    """
    roles = [
        Role(
            company=role.company,
            title=role.title,
            start=role.start,
            end=role.end,
        )
        for role in struct.roles
    ]
    return IdentityLedger(name=name, contact=contact, roles=roles)


def assert_ledger_matches_source(
    ledger: IdentityLedger, resume_tex_raw: str
) -> None:
    """Guard: every identity string must appear verbatim in the source .tex.

    Defensive check against the model paraphrasing/reformatting identity fields.
    Raises ValueError listing the drifted field(s) on any mismatch.
    """
    drifted: list[str] = []
    for index, role in enumerate(ledger.roles):
        for field in _IDENTITY_FIELDS:
            value = getattr(role, field)
            if value not in resume_tex_raw:
                drifted.append(
                    f"role[{index}].{field}={value!r} not found verbatim in "
                    f"source .tex (identity field was altered/paraphrased)"
                )
    if drifted:
        raise ValueError(
            "IdentityLedger drift detected - identity fields must be "
            "character-exact copies of the source:\n" + "\n".join(drifted)
        )


def parse_resume(state: PipelineState) -> dict:
    """Node: parse the raw resume and derive its identity ledger.

    Skips the parser LLM call entirely when ``resume_struct`` and
    ``identity_ledger`` are already present in state - seeded by a caller that
    parsed this exact resume once already (e.g. a batch run reusing one parse
    across many JDs instead of re-parsing per JD).
    """
    cached_struct = state.get("resume_struct")
    cached_ledger = state.get("identity_ledger")
    if cached_struct is not None and cached_ledger is not None:
        log.info("parse_resume | resume_struct/identity_ledger cached - skipping LLM call")
        return {"resume_struct": cached_struct, "identity_ledger": cached_ledger}

    resume_tex_raw = state["resume_tex_raw"]
    log.info("parse_resume | sending %d chars to %s", len(resume_tex_raw), MODEL_FAST)
    struct = parse_fast(PARSER_SYSTEM, resume_tex_raw, ResumeStruct)
    name = extract_name(resume_tex_raw)
    contact = extract_contact(resume_tex_raw)
    ledger = derive_ledger(struct, name=name, contact=contact)
    log.info(
        "parse_resume | done - candidate=%r, %d roles, %d skills, ledger locked",
        name, len(struct.roles), len(struct.skills),
    )
    return {"resume_struct": struct, "identity_ledger": ledger}
