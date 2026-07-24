"""Tests for the LaTeX renderer — integrity guarantee #1 (structural).

The renderer patches the original .tex in-place: only the itemize bullet
blocks are replaced; everything else (fonts, formatting, sections) is preserved.
Every injected bullet string is LaTeX-escaped.
"""
from src.compiler.renderer import latex_escape, render
from src.pipeline.schemas import (
    IdentityLedger,
    Role,
    RoleBullets,
    WriterOutput,
)


def _ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Ada Lovelace",
        contact="ada@example.com | 555-0100",
        roles=[
            Role(
                company="Analytical Engines Inc",
                title="Lead Engineer",
                start="Jan 2020",
                end="Present",
            ),
            Role(
                company="Babbage & Co",
                title="Research Fellow",
                start="Jun 2016",
                end="Dec 2019",
            ),
        ],
    )


def _writer() -> WriterOutput:
    return WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Led a team of 5 engineers"]),
            RoleBullets(index=1, bullets=["Published 3 papers"]),
        ],
    )


def _original_tex() -> str:
    """Minimal original .tex matching the two roles in _ledger()."""
    return r"""
\documentclass{article}
\begin{document}
{\Huge Ada Lovelace}\par
ada@example.com | 555-0100\par
\section*{Experience}
\textbf{Analytical Engines Inc} \hfill Jan 2020 -- Present\par
{\itshape Lead Engineer}\par
\begin{itemize}
  \item Original bullet 1
\end{itemize}
\textbf{Babbage \& Co} \hfill Jun 2016 -- Dec 2019\par
{\itshape Research Fellow}\par
\begin{itemize}
  \item Original bullet A
\end{itemize}
\end{document}
"""


# --- latex_escape ------------------------------------------------------------


def test_latex_escape_special_characters():
    assert latex_escape("&") == r"\&"
    assert latex_escape("%") == r"\%"
    assert latex_escape("#") == r"\#"
    assert latex_escape("_") == r"\_"
    assert latex_escape("$") == r"\$"
    assert latex_escape("{") == r"\{"
    assert latex_escape("}") == r"\}"
    assert latex_escape("~") == r"\textasciitilde{}"
    assert latex_escape("^") == r"\textasciicircum{}"


def test_latex_escape_backslash_first():
    # Backslash must be escaped first so we do not double-escape the
    # replacement sequences of other characters.
    assert latex_escape("\\") == r"\textbackslash{}"
    # A backslash followed by an ampersand must not become a mangled escape.
    assert latex_escape("a\\&b") == r"a\textbackslash{}\&b"


def test_latex_escape_plain_text_unchanged():
    assert latex_escape("Hello World 123") == "Hello World 123"


# --- render: identity fields verbatim ----------------------------------------


def test_render_injects_locked_identity_fields_verbatim():
    # Identity fields come from original_tex verbatim — patch leaves them untouched.
    out = render(_original_tex(), _ledger(), _writer())
    assert "Ada Lovelace" in out
    assert "ada@example.com | 555-0100" in out
    assert "ada@example.com" in out
    for company in ("Analytical Engines Inc", "Babbage \\& Co"):
        assert company in out
    for title in ("Lead Engineer", "Research Fellow"):
        assert title in out
    for date in ("Jan 2020", "Present", "Jun 2016", "Dec 2019"):
        assert date in out


def test_render_injects_writer_bullets():
    # Only bullets are patched; skills stay from the original .tex.
    out = render(_original_tex(), _ledger(), _writer())
    assert "Led a team of 5 engineers" in out
    assert "Published 3 papers" in out
    # Original bullets are gone.
    assert "Original bullet 1" not in out
    assert "Original bullet A" not in out


# --- render: escaping of writer content --------------------------------------


def test_render_escapes_special_chars_in_bullets():
    ledger = _ledger()
    writer = WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Cut costs by 30% & boosted C_speed"]),
            RoleBullets(index=1, bullets=["Saved $1M on #infra"]),
        ],
    )
    out = render(_original_tex(), ledger, writer)
    # Raw specials in bullets must NOT appear unescaped.
    assert "30% &" not in out
    assert r"30\% \& boosted C\_speed" in out
    assert r"\$1M on \#infra" in out


# --- render: writer content NEVER leaks into an identity slot ----------------


def test_writer_output_never_reaches_identity_slot():
    """Writer bullets cannot overwrite or inject company/title/date slots.

    The patch approach replaces only itemize blocks; role headers in the
    original .tex are untouched. Even if a bullet text impersonates a company
    name it can only appear inside an itemize block, never as a role header.
    """
    ledger = _ledger()
    malicious = WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["FAKE COMPANY LLC as Chief Fraud Officer"]),
            RoleBullets(index=1, bullets=["Worked at Shadow Corp"]),
        ],
    )
    out = render(_original_tex(), ledger, malicious)
    # Ledger identity from original .tex is preserved.
    assert "Analytical Engines Inc" in out
    assert "Lead Engineer" in out
    # The malicious bullet appears only AFTER the real company header, never before.
    assert "FAKE COMPANY LLC" not in out.split("Analytical Engines Inc")[0]


def test_render_matches_bullets_by_role_index():
    """Bullets are matched to ledger roles by RoleBullets.index, order-independent."""
    ledger = _ledger()
    writer = WriterOutput(
        roles=[
            RoleBullets(index=1, bullets=["SECOND ROLE BULLET"]),
            RoleBullets(index=0, bullets=["FIRST ROLE BULLET"]),
        ],
    )
    out = render(_original_tex(), ledger, writer)
    # Role 0 (Analytical Engines) must be paired with FIRST ROLE BULLET.
    first_role_block = out.split("Babbage \\& Co")[0]
    assert "FIRST ROLE BULLET" in first_role_block
    assert "SECOND ROLE BULLET" not in first_role_block


# --- render: bold formatting preserved ---------------------------------------


def _main_tex_style() -> str:
    """Fixture using the actual main.tex format: bold title, company in braces."""
    return r"""\documentclass[11pt]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{enumitem}
\begin{document}
\centerline{\Huge Test User}
\centerline{test@example.com}
\section*{Experience}
\textbf{Software Engineer,} {AcmeCorp} -- New York, NY \hfill Jan 2024 -- Present \\
\vspace{-9pt}
\begin{itemize}
    \item Original bullet one
    \item Original bullet two
\end{itemize}
\textbf{Junior Developer,} {StartupXYZ} -- Remote \hfill Jun 2022 -- Dec 2023 \\
\vspace{-9pt}
\begin{itemize}
    \item Old work item A
\end{itemize}
\section*{Projects}
\textbf{CoolProject} \hfill https://example.com \\
\vspace{-9pt}
\begin{itemize}
  \item Project bullet stays frozen
\end{itemize}
\end{document}
"""


def _main_tex_ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Test User",
        contact="test@example.com",
        roles=[
            Role(company="AcmeCorp", title="Software Engineer", start="Jan 2024", end="Present"),
            Role(company="StartupXYZ", title="Junior Developer", start="Jun 2022", end="Dec 2023"),
        ],
    )


def _main_tex_writer() -> WriterOutput:
    return WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Increased throughput by rewriting pipeline in Go"]),
            RoleBullets(index=1, bullets=["Reduced latency using Redis caching layer"]),
        ],
    )


def test_bold_role_title_preserved_after_patch():
    r"""\textbf{Role,} in role header lines must survive bullet replacement intact."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    assert r"\textbf{Software Engineer,}" in out
    assert r"\textbf{Junior Developer,}" in out


def test_company_braces_preserved_after_patch():
    """Company name in {braces} must survive bullet replacement intact."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    assert "{AcmeCorp}" in out
    assert "{StartupXYZ}" in out


def test_vspace_between_header_and_itemize_preserved():
    r"""The \vspace{-9pt} between role header and \begin{itemize} must survive."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    assert r"\vspace{-9pt}" in out


def test_project_section_bold_untouched():
    r"""\textbf{ProjectName} in frozen Projects section must not be altered."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    assert r"\textbf{CoolProject}" in out
    assert "Project bullet stays frozen" in out


def test_project_section_bullets_not_replaced():
    """Project itemize blocks must never be patched (projects are frozen)."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    assert "Project bullet stays frozen" in out
    # Experience bullets must be replaced.
    assert "Original bullet one" not in out
    assert "Old work item A" not in out


def test_new_experience_bullets_appear_in_correct_roles():
    """Writer bullets land under their matching company, not in the wrong role."""
    out = render(_main_tex_style(), _main_tex_ledger(), _main_tex_writer())
    before_startup = out.split("StartupXYZ")[0]
    assert "Increased throughput" in before_startup
    assert "Reduced latency" not in before_startup


# --- render: tectonic font normalization (bold-loss fix) ---------------------
#
# The root cause of "bold disappears in the PDF": the source loads XCharter via
# the pdfLaTeX Type1 path (\usepackage{XCharter} + [T1]{fontenc} + inputenc).
# Under tectonic's XeTeX engine that path silently falls back to a bold-less
# font, flattening EVERY \textbf in the document. render() must convert the font
# setup to the XeTeX-native fontspec path so the bold face loads.


def _xcharter_tex() -> str:
    """A resume preamble using the pdfLaTeX-era XCharter font setup."""
    return r"""\documentclass[11pt]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage[normalem]{ulem}
\usepackage{XCharter}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\begin{document}
\section*{Experience}
\textbf{Software Engineer,} {AcmeCorp} -- NY \hfill Jan 2024 -- Present \\
\begin{itemize}
  \item Original bullet
\end{itemize}
\end{document}
"""


def _xcharter_ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Test User",
        contact="t@x.com",
        roles=[Role(company="AcmeCorp", title="Software Engineer", start="Jan 2024", end="Present")],
    )


def _xcharter_writer() -> WriterOutput:
    return WriterOutput(
        roles=[RoleBullets(index=0, bullets=["New optimized bullet"])],
    )


def test_xcharter_converted_to_fontspec():
    """\\usepackage{XCharter} must become the fontspec path so bold loads."""
    out = render(_xcharter_tex(), _xcharter_ledger(), _xcharter_writer())
    assert r"\usepackage{fontspec}" in out
    assert r"\setmainfont{XCharter}" in out
    assert r"\usepackage{XCharter}" not in out


def test_legacy_encoding_packages_dropped_on_conversion():
    """T1 fontenc and inputenc break the XeTeX font path; drop them."""
    out = render(_xcharter_tex(), _xcharter_ledger(), _xcharter_writer())
    assert "fontenc" not in out
    assert "inputenc" not in out


def test_fontspec_loaded_before_setmainfont():
    r"""\setmainfont is undefined until fontspec loads — order matters."""
    out = render(_xcharter_tex(), _xcharter_ledger(), _xcharter_writer())
    assert out.index(r"\usepackage{fontspec}") < out.index(r"\setmainfont{XCharter}")


def test_font_conversion_preserves_bold_markup_and_body():
    """Conversion touches only the preamble; \\textbf headers and body survive."""
    out = render(_xcharter_tex(), _xcharter_ledger(), _xcharter_writer())
    assert r"\textbf{Software Engineer,}" in out
    assert "{AcmeCorp}" in out
    assert "New optimized bullet" in out
    # Non-font packages are untouched.
    assert r"\usepackage[margin=0.5in]{geometry}" in out
    assert r"\usepackage{enumitem}" in out
    assert r"\usepackage[hidelinks]{hyperref}" in out


def test_no_font_conversion_when_no_known_font_package():
    """Docs without a convertible font package keep their preamble verbatim."""
    plain = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{enumitem}
\begin{document}
\section*{Experience}
\textbf{Engineer} {AcmeCorp}\par
\begin{itemize}
  \item Old
\end{itemize}
\end{document}
"""
    ledger = IdentityLedger(
        name="U", contact="c",
        roles=[Role(company="AcmeCorp", title="Engineer", start="", end="")],
    )
    writer = WriterOutput(roles=[RoleBullets(index=0, bullets=["New"])])
    out = render(plain, ledger, writer)
    # No fontspec injected; existing (harmless, working) fontenc left alone.
    assert r"\usepackage{fontspec}" not in out
    assert r"\usepackage[T1]{fontenc}" in out
