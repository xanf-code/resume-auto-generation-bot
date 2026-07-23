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
        skills=["Python", "LaTeX"],
        summary="Pioneering engineer with decades of impact.",
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
    # Only bullets are patched; skills/summary stay from the original .tex.
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
        skills=["C++ & Rust", "50%_uptime"],
        summary="Delivered value$ across teams.",
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
        skills=["Impersonation"],
        summary="I worked at Totally Real Bank.",
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
        skills=["S"],
        summary="sum",
    )
    out = render(_original_tex(), ledger, writer)
    # Role 0 (Analytical Engines) must be paired with FIRST ROLE BULLET.
    first_role_block = out.split("Babbage \\& Co")[0]
    assert "FIRST ROLE BULLET" in first_role_block
    assert "SECOND ROLE BULLET" not in first_role_block
