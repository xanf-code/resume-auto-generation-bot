"""Deterministic LaTeX renderer - integrity guarantee #1 (structural).

Patches the user's original ``.tex`` file in-place: only the
``\\begin{itemize}...\\end{itemize}`` block immediately following each role's
company-name anchor is replaced with the writer's new bullets. Every other
byte - packages, fonts, section formatting, skills, education - is
preserved verbatim from the original file.

A ``%% ROLE-HEADER %%`` comment is injected before each role's anchor line so
the identity tripwire can count roles without relying on Jinja template markers.
Every injected bullet string is LaTeX-escaped (backslash first).
"""
import logging
import re

from src.pipeline.schemas import IdentityLedger, ProjectBullets, SelectedProject, WriterOutput

log = logging.getLogger(__name__)

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


# pdfLaTeX-era font packages whose Type1 loading path misbehaves under
# tectonic's XeTeX engine: the OTF request silently falls back to a bold-less
# font, flattening EVERY ``\textbf`` in the document. Each maps its
# ``\usepackage{<pkg>}`` to the fontspec ``\setmainfont`` name that restores the
# bold face via the XeTeX-native path. Extend this map for other OTF-available
# font packages as they come up.
_FONTSPEC_CONVERTIBLE: dict[str, str] = {
    "XCharter": "XCharter",
}

# Legacy encoding packages that are unnecessary - and actively harmful - under
# XeTeX once the main font is loaded via fontspec. fontspec manages Unicode
# encoding itself; leaving these in forces the legacy path that drops bold.
_LEGACY_ENCODING_PKGS = frozenset({"fontenc", "inputenc"})

# Matches ``\usepackage`` with optional ``[options]`` and captures the braced
# package list (``\usepackage[T1]{fontenc}`` → ``fontenc``).
_USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}")


def _normalize_fonts_for_tectonic(tex: str) -> str:
    """Convert a pdfLaTeX font setup to the XeTeX-native fontspec path.

    Only acts when the document loads a known convertible font package (see
    ``_FONTSPEC_CONVERTIBLE``). In that case it:

    1. Replaces ``\\usepackage{<font>}`` with ``\\usepackage{fontspec}`` +
       ``\\setmainfont{<font>}`` (fontspec injected once, before the first
       ``\\setmainfont`` so the command is defined when used).
    2. Drops legacy ``fontenc`` / ``inputenc`` packages, which force the Type1
       path that silently loses the bold face under tectonic.

    Documents without a convertible font package are returned unchanged - their
    preamble (including a plain, working ``fontenc``) is left verbatim.
    """
    fonts_present = {
        pkg: mainfont
        for pkg, mainfont in _FONTSPEC_CONVERTIBLE.items()
        if re.search(r"\\usepackage(?:\[[^\]]*\])?\{" + re.escape(pkg) + r"\}", tex)
    }
    if not fonts_present:
        return tex

    out_lines: list[str] = []
    fontspec_injected = False
    for line in tex.splitlines(keepends=True):
        match = _USEPACKAGE_RE.search(line)
        if match:
            pkgs = [p.strip() for p in match.group(1).split(",")]
            # Drop legacy encoding packages entirely.
            if any(p in _LEGACY_ENCODING_PKGS for p in pkgs):
                continue
            # Convert a known font package to the fontspec path.
            font_hit = next((p for p in pkgs if p in fonts_present), None)
            if font_hit is not None:
                newline = "\n" if line.endswith("\n") else ""
                prefix = "" if fontspec_injected else "\\usepackage{fontspec}\n"
                fontspec_injected = True
                out_lines.append(
                    f"{prefix}\\setmainfont{{{fonts_present[font_hit]}}}{newline}"
                )
                continue
        out_lines.append(line)
    return "".join(out_lines)


def _link_display(link: str) -> str:
    """Strip protocol and trailing slash for display: 'https://foo.com/' → 'foo.com'."""
    display = link.removeprefix("https://").removeprefix("http://")
    return display.rstrip("/")


# A project entry header in the Projects section:
#   \textbf{<heading>} \hfill \href{<url>}{<display>} \\
# The \href requirement distinguishes project headers from Experience role
# headers, which use \hfill for dates but carry no \href.
_PROJECT_HEADER_RE = re.compile(
    r"\\textbf\{(?P<heading>[^{}]*)\}(?P<mid>\s*\\hfill\s*)"
    r"\\href\{(?P<url>[^{}]*)\}\{(?P<display>[^{}]*)\}"
)


def _projects_section_span(tex: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` byte offsets of the Projects section body.

    ``start`` is just past ``\\section*{Projects}``; ``end`` is the next
    ``\\section*{`` or ``\\end{document}``. Returns ``None`` when absent.
    """
    marker = r"\section*{Projects}"
    section_start = tex.find(marker)
    if section_start == -1:
        return None

    after = section_start + len(marker)
    next_section = tex.find(r"\section*{", after)
    end_doc = tex.find(r"\end{document}", after)

    candidates = [p for p in (next_section, end_doc) if p != -1]
    if not candidates:
        return None
    return after, min(candidates)


def patch_project_bullets(
    tex: str,
    selected_projects: list[SelectedProject],
    project_bullets: list[ProjectBullets],
) -> str:
    """Surgically replace project headings, links, and bullets in ``tex``.

    Mirrors ``patch_bullets``' integrity guarantee: within the Projects section,
    only the heading text, the ``\\href`` target/display, and the ``\\item``
    contents of each entry's itemize block are replaced. Every other byte -
    ``\\vspace`` values, comments, blank lines, the section header itself - is
    preserved verbatim from the original template.

    Entries are matched positionally: the Nth project header in the template
    receives the bullets for rank N. Surplus template entries beyond the number
    of generated projects are left untouched rather than deleted, so a template
    mismatch degrades visibly instead of silently dropping content.

    Returns ``tex`` unchanged when the Projects section is absent or either
    input list is empty.
    """
    if not selected_projects or not project_bullets:
        return tex

    span = _projects_section_span(tex)
    if span is None:
        return tex
    body_start, body_end = span

    bullets_by_rank: dict[int, ProjectBullets] = {pb.rank: pb for pb in project_bullets}
    link_by_rank: dict[int, str] = {sp.rank: sp.link for sp in selected_projects}
    ranks = sorted(bullets_by_rank)

    # Collect patches within the section body, then apply back-to-front so
    # earlier byte offsets stay valid (same strategy as patch_bullets).
    patches: list[tuple[int, int, str]] = []
    search_from = body_start

    for rank in ranks:
        pb = bullets_by_rank[rank]
        match = _PROJECT_HEADER_RE.search(tex, search_from, body_end)
        if match is None:
            log.warning(
                "renderer | no template slot for project rank=%d - skipping", rank
            )
            continue

        link = link_by_rank.get(rank, match.group("url"))
        patches.append(
            (
                match.start(),
                match.end(),
                f"\\textbf{{{latex_escape(pb.heading)}}}{match.group('mid')}"
                f"\\href{{{link}}}{{{_link_display(link)}}}",
            )
        )

        block = _find_next_itemize(tex, match.end())
        if block is None or block[0] >= body_end:
            search_from = match.end()
            continue

        block_start, block_end = block
        patches.append((block_start, block_end, _build_itemize_block(pb.bullets)))
        search_from = block_end

    result = tex
    for start, end, replacement in sorted(patches, key=lambda p: p[0], reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def render(
    original_tex: str,
    identity_ledger: IdentityLedger,
    writer_output: WriterOutput,
) -> str:
    """Patch ``original_tex`` in-place: replace bullet blocks per role.

    The original document's packages, fonts, formatting, skills, and
    education sections are left verbatim. Only the ``\\begin{itemize}...
    \\end{itemize}`` block immediately following each role's anchor is replaced
    with the writer's optimised bullets. pdfTeX-only directives that break
    tectonic are stripped, and a pdfLaTeX font setup (e.g. XCharter + T1
    fontenc) is converted to the fontspec path so bold faces survive compilation.
    """
    patched = patch_bullets(original_tex, identity_ledger, writer_output)
    patched = _strip_tectonic_incompatible(patched)
    return _normalize_fonts_for_tectonic(patched)
