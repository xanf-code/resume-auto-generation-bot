"""Deterministic LaTeX renderer — integrity guarantee #1 (structural).

Patches the user's original ``.tex`` file in-place: only the
``\\begin{itemize}...\\end{itemize}`` block immediately following each role's
company-name anchor is replaced with the writer's new bullets. Every other
byte — packages, fonts, section formatting, summary, skills, education — is
preserved verbatim from the original file.

A ``%% ROLE-HEADER %%`` comment is injected before each role's anchor line so
the identity tripwire can count roles without relying on Jinja template markers.
Every injected bullet string is LaTeX-escaped (backslash first).
"""
from src.pipeline.schemas import IdentityLedger, WriterOutput

# LaTeX comment injected before each role header so identity_check can count
# roles correctly. Must start with % to be a valid LaTeX comment.
ROLE_HEADER_MARKER = "%% ROLE-HEADER %%"

# LaTeX special character → replacement map. Applied in a SINGLE left-to-right
# pass (character by character) so replacement sequences that themselves
# contain braces (e.g. ``\textbackslash{}``) are never re-escaped.
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

    Handles ``& % # _ $ { } ~ ^ \\``. Single character-by-character pass so
    the braces introduced by replacements are never re-escaped.
    """
    return "".join(_LATEX_ESCAPE_MAP.get(ch, ch) for ch in s)


def _find_next_itemize(tex: str, after: int) -> tuple[int, int] | None:
    """Return ``(block_start, block_end)`` of the next itemize after ``after``.

    ``block_end`` points one past the closing ``\\end{itemize}``. Returns
    ``None`` if no complete itemize block is found.
    """
    begin = tex.find(r"\begin{itemize}", after)
    if begin == -1:
        return None
    end_tag = tex.find(r"\end{itemize}", begin)
    if end_tag == -1:
        return None
    return begin, end_tag + len(r"\end{itemize}")


def _build_itemize_block(bullets: list[str]) -> str:
    """Build an escaped ``\\begin{itemize}...\\end{itemize}`` block."""
    items = "\n".join(f"  \\item {latex_escape(b)}" for b in bullets)
    return f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}"


def patch_bullets(
    original_tex: str,
    identity_ledger: IdentityLedger,
    writer_output: WriterOutput,
) -> str:
    """Surgically replace only the bullet ``\\item`` blocks in ``original_tex``.

    For each ledger role (in order) the function:

    1. Locates the role's company name in the source (tries the raw string
       first; falls back to the LaTeX-escaped form for names containing ``&``
       etc.).
    2. Injects a ``%% ROLE-HEADER %%`` comment before the role's line so the
       identity tripwire can count roles without Jinja markers.
    3. Finds the next ``\\begin{itemize}...\\end{itemize}`` block after the
       anchor and replaces it with the writer's bullets for that role.

    Roles for which the writer produced no bullets are left unchanged.
    All patches are collected first then applied back-to-front so earlier
    byte offsets stay valid.
    """
    bullets_by_index: dict[int, list[str]] = {
        rb.index: list(rb.bullets) for rb in writer_output.roles
    }

    patches: list[tuple[int, int, str]] = []
    search_from = 0

    for idx, role in enumerate(identity_ledger.roles):
        new_bullets = bullets_by_index.get(idx)

        # Locate role anchor: raw string first, latex-escaped fallback.
        anchor = original_tex.find(role.company, search_from)
        if anchor == -1:
            anchor = original_tex.find(latex_escape(role.company), search_from)
        if anchor == -1:
            anchor = original_tex.find(role.title, search_from)
        if anchor == -1:
            anchor = original_tex.find(latex_escape(role.title), search_from)
        if anchor == -1:
            continue

        # Inject ROLE_HEADER_MARKER as a LaTeX comment before this role's line.
        line_start = original_tex.rfind("\n", 0, anchor) + 1
        if not original_tex[line_start:].startswith(ROLE_HEADER_MARKER):
            patches.append((line_start, line_start, f"{ROLE_HEADER_MARKER}\n"))

        # Find the next itemize block after the anchor.
        block = _find_next_itemize(original_tex, anchor)
        if block is None:
            search_from = anchor + 1
            continue

        block_start, block_end = block
        search_from = block_end

        # Only replace the block when the writer produced bullets for this role.
        if new_bullets:
            patches.append((block_start, block_end, _build_itemize_block(new_bullets)))

    # Apply back-to-front so earlier offsets stay valid.
    result = original_tex
    for start, end, replacement in sorted(patches, key=lambda p: p[0], reverse=True):
        result = result[:start] + replacement + result[end:]

    return result


# pdfTeX-only directives that tectonic's XeTeX engine cannot handle.
_TECTONIC_STRIP = (
    r"\input{glyphtounicode}",
    r"\pdfgentounicode=1",
)


def _strip_tectonic_incompatible(tex: str) -> str:
    """Remove pdfTeX-only directives that break tectonic compilation.

    ``\\input{glyphtounicode}`` and ``\\pdfgentounicode=1`` are pdfTeX
    primitives that tectonic's XeTeX engine cannot process. They exist only
    to make PDF output machine-readable; tectonic already produces
    Unicode-tagged output without them.
    """
    lines = []
    for line in tex.splitlines(keepends=True):
        stripped = line.strip()
        if any(stripped.startswith(directive) for directive in _TECTONIC_STRIP):
            continue
        lines.append(line)
    return "".join(lines)


def render(
    original_tex: str,
    identity_ledger: IdentityLedger,
    writer_output: WriterOutput,
) -> str:
    """Patch ``original_tex`` in-place: replace bullet blocks per role.

    The original document's packages, fonts, formatting, summary, skills, and
    education sections are left verbatim. Only the ``\\begin{itemize}...
    \\end{itemize}`` block immediately following each role's anchor is replaced
    with the writer's optimised bullets. pdfTeX-only directives that break
    tectonic are stripped before returning.
    """
    patched = patch_bullets(original_tex, identity_ledger, writer_output)
    return _strip_tectonic_incompatible(patched)
