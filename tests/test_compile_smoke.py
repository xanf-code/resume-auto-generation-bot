"""Real tectonic compile smoke test — no LLM, fully deterministic.

Hand-builds an IdentityLedger + WriterOutput, renders, then compiles with the
real tectonic binary and asserts a non-empty PDF was produced. The first run
may download packages, so this single test uses a longer compile timeout.
"""
import os

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
        summary="Mathematician & founder of theoretical computer science.",
    )


def test_compile_smoke_produces_pdf(tmp_path):
    tex_source = render(_ledger(), _writer())
    ok, pdf_path, errors = compile_tex(
        tex_source, workdir=str(tmp_path), timeout=_SMOKE_COMPILE_TIMEOUT
    )
    assert ok is True, f"compile failed: {errors}"
    assert pdf_path is not None
    assert os.path.isfile(pdf_path)
    assert os.path.getsize(pdf_path) > 0
    assert errors == []
