"""Real tectonic compile smoke test — no LLM, fully deterministic.

Hand-builds an IdentityLedger + WriterOutput, renders, then compiles with the
real tectonic binary and asserts a non-empty PDF was produced. The first run
may download packages, so this single test uses a longer compile timeout.
"""
import os
import shutil
import subprocess

import pytest

from src.compiler.renderer import render
from src.compiler.tectonic import compile_tex
from src.pipeline.schemas import (
    IdentityLedger,
    Role,
    RoleBullets,
    WriterOutput,
)

# First-run package fetch can exceed the 60s production default; bump this
# single smoke test to 120s while keeping the production default at 60.
_SMOKE_COMPILE_TIMEOUT = 120


def _ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Alan Turing",
        contact="alan@bletchley.uk | +44 555 0100",
        roles=[
            Role(
                company="Government Code & Cypher School",
                title="Cryptanalyst",
                start="1938",
                end="1945",
            ),
            Role(
                company="University of Manchester",
                title="Reader in Mathematics",
                start="1948",
                end="1954",
            ),
        ],
    )


def _writer() -> WriterOutput:
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "Designed the Bombe, cutting decryption time by 90%",
                    "Broke the Enigma & Lorenz ciphers under $1M budget",
                ],
            ),
            RoleBullets(
                index=1,
                bullets=[
                    "Authored foundational work on computability",
                    "Advanced early stored-program computing_theory",
                ],
            ),
        ],
        skills=["Cryptanalysis", "Computability Theory", "C++ & Assembly"],
    )


def _original_tex() -> str:
    """Minimal compilable original .tex matching the two roles in _ledger()."""
    return r"""
\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{enumitem}
\setlist[itemize]{leftmargin=1.5em, itemsep=1pt, topsep=2pt}
\pagenumbering{gobble}
\setlength{\parindent}{0pt}
\begin{document}
{\Huge\bfseries Alan Turing}\par
\vspace{2pt}
alan@bletchley.uk | +44 555 0100\par
\vspace{4pt}
\textbf{Experience}\par
\vspace{2pt}\hrule\vspace{4pt}
\textbf{Government Code \& Cypher School} \hfill 1938 -- 1945\par
{\itshape Cryptanalyst}\par
\begin{itemize}
  \item Original bullet one
\end{itemize}
\vspace{4pt}
\textbf{University of Manchester} \hfill 1948 -- 1954\par
{\itshape Reader in Mathematics}\par
\begin{itemize}
  \item Original bullet two
\end{itemize}
\end{document}
"""


def test_compile_smoke_produces_pdf(tmp_path):
    tex_source = render(_original_tex(), _ledger(), _writer())
    ok, pdf_path, errors = compile_tex(
        tex_source, workdir=str(tmp_path), timeout=_SMOKE_COMPILE_TIMEOUT
    )
    assert ok is True, f"compile failed: {errors}"
    assert pdf_path is not None
    assert os.path.isfile(pdf_path)
    assert os.path.getsize(pdf_path) > 0
    assert errors == []


# --- XCharter bold regression guard ------------------------------------------
#
# Guards the exact bug where a pdfLaTeX XCharter setup compiled under tectonic
# lost EVERY bold face (silent fallback to a bold-less font). render() converts
# to fontspec; a correct compile must embed an XCharter BOLD face.


def _xcharter_tex() -> str:
    return r"""\documentclass[11pt]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{XCharter}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{enumitem}
\begin{document}
\section*{Experience}
\textbf{Government Code \& Cypher School} \hfill 1938 -- 1945\par
{\itshape Cryptanalyst}\par
\begin{itemize}
  \item Original bullet one
\end{itemize}
\end{document}
"""


def _xcharter_ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Alan Turing", contact="alan@bletchley.uk",
        roles=[Role(company="Government Code & Cypher School",
                    title="Cryptanalyst", start="1938", end="1945")],
    )


def _xcharter_writer() -> WriterOutput:
    return WriterOutput(
        roles=[RoleBullets(index=0, bullets=["Designed the Bombe under budget"])],
        skills=["Cryptanalysis"],
    )


def _embedded_fonts(pdf_path: str) -> str:
    """Return pdffonts output for the PDF (font-dictionary decode)."""
    result = subprocess.run(  # nosec B603 B607
        ["pdffonts", pdf_path], capture_output=True, text=True, timeout=15
    )
    return result.stdout


def test_xcharter_resume_compiles_with_bold_face(tmp_path):
    """An XCharter resume must compile AND embed a bold face under tectonic."""
    tex_source = render(_xcharter_tex(), _xcharter_ledger(), _xcharter_writer())
    ok, pdf_path, errors = compile_tex(
        tex_source, workdir=str(tmp_path), timeout=_SMOKE_COMPILE_TIMEOUT
    )
    assert ok is True, f"XCharter compile failed: {errors}"
    assert pdf_path is not None and os.path.isfile(pdf_path)

    if shutil.which("pdffonts") is None:
        pytest.skip("pdffonts (poppler) not available — cannot verify bold face")

    fonts = _embedded_fonts(pdf_path)
    assert "Bold" in fonts, (
        "no bold font face embedded — \\textbf silently flattened. "
        f"Embedded fonts:\n{fonts}"
    )
