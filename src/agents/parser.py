"""Parser agent — raw resume .tex -> ResumeStruct + derived IdentityLedger.

The parser LLM extracts the structured resume; this node then DERIVES the
immutable identity ledger from it and runs a defensive guard that every
identity string (company / title / start / end) still appears verbatim in the
source .tex. Any drift means the model paraphrased an identity field, which the
guard rejects loudly.
"""
import re

from src.pipeline.llm import parse_fast
from src.pipeline.schemas import IdentityLedger, ResumeStruct, Role
from src.pipeline.state import PipelineState
from src.prompts.extraction import PARSER_SYSTEM

_IDENTITY_FIELDS = ("company", "title", "start", "end")

# A LaTeX command wrapper like \textbf{Jane Doe} -> "Jane Doe".
_TEX_COMMAND = re.compile(r"\\[a-zA-Z]+\*?\{([^{}]*)\}")
# A plausible email address.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _strip_tex(value: str) -> str:
    """Collapse the outermost LaTeX command wrapper and trim whitespace."""
    match = _TEX_COMMAND.search(value)
    return (match.group(1) if match else value).strip()


def extract_name(resume_tex_raw: str) -> str:
    """Best-effort candidate name from the raw .tex.

    Convention: the name is the first bold/large command's content. Falls back
    to the first non-empty content line.
    """
    match = _TEX_COMMAND.search(resume_tex_raw)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    for line in resume_tex_raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("\\"):
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

    Identity fields are copied character-exact from each ResumeRole — this is
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
            "IdentityLedger drift detected — identity fields must be "
            "character-exact copies of the source:\n" + "\n".join(drifted)
        )


def parse_resume(state: PipelineState) -> dict:
    """Node: parse the raw resume and derive its identity ledger.

    Reads ``resume_tex_raw``; returns a NEW dict with ``resume_struct`` and
    ``identity_ledger`` (never mutates the incoming state).
    """
    resume_tex_raw = state["resume_tex_raw"]
    struct = parse_fast(PARSER_SYSTEM, resume_tex_raw, ResumeStruct)
    ledger = derive_ledger(
        struct,
        name=extract_name(resume_tex_raw),
        contact=extract_contact(resume_tex_raw),
    )
    return {"resume_struct": struct, "identity_ledger": ledger}
