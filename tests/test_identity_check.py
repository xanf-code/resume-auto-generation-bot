"""Tests for the mechanical identity tripwire — integrity guarantee #2.

check_identity diffs rendered LaTeX against the ledger. Any tamper (changed
date, renamed company, altered title, injected extra role) must fail loudly.
"""
from src.compiler.identity_check import check_identity
from src.compiler.renderer import render
from src.pipeline.schemas import (
    IdentityLedger,
    Role,
    RoleBullets,
    WriterOutput,
)


def _ledger() -> IdentityLedger:
    return IdentityLedger(
        name="Grace Hopper",
        contact="grace@navy.mil",
        roles=[
            Role(
                company="US Navy",
                title="Rear Admiral",
                start="1943",
                end="1986",
            ),
            Role(
                company="Remington Rand",
                title="Senior Programmer",
                start="1949",
                end="1959",
            ),
        ],
    )


def _writer() -> WriterOutput:
    return WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Invented the compiler concept"]),
            RoleBullets(index=1, bullets=["Developed FLOW-MATIC"]),
        ],
        skills=["COBOL", "Leadership"],
        summary="Computing pioneer.",
    )


def test_check_identity_passes_for_faithful_render():
    ledger = _ledger()
    rendered = render(ledger, _writer())
    ok, violations = check_identity(rendered, ledger)
    assert ok is True
    assert violations == []


# --- Four distinct tamper cases: each must FAIL LOUDLY -----------------------


def test_tamper_changed_date_fails():
    ledger = _ledger()
    rendered = render(ledger, _writer())
    # Tamper: rewrite the Navy end date 1986 -> 1999.
    tampered = rendered.replace("1986", "1999")
    ok, violations = check_identity(tampered, ledger)
    assert ok is False
    assert violations
    assert any("1986" in v for v in violations)


def test_tamper_renamed_company_fails():
    ledger = _ledger()
    rendered = render(ledger, _writer())
    # Tamper: rename 'US Navy' to 'US Marines'.
    tampered = rendered.replace("US Navy", "US Marines")
    ok, violations = check_identity(tampered, ledger)
    assert ok is False
    assert violations
    assert any("US Navy" in v for v in violations)


def test_tamper_altered_title_fails():
    ledger = _ledger()
    rendered = render(ledger, _writer())
    # Tamper: alter 'Rear Admiral' to 'Fleet Admiral'.
    tampered = rendered.replace("Rear Admiral", "Fleet Admiral")
    ok, violations = check_identity(tampered, ledger)
    assert ok is False
    assert violations
    assert any("Rear Admiral" in v for v in violations)


def test_tamper_injected_extra_role_fails():
    ledger = _ledger()
    rendered = render(ledger, _writer())
    # Tamper: smuggle in an EXTRA role header beyond the ledger's two roles.
    # We duplicate an existing role-header marker block so the header count
    # exceeds len(ledger.roles).
    from src.compiler.renderer import ROLE_HEADER_MARKER

    injected = rendered + (
        "\n" + ROLE_HEADER_MARKER + "\n"
        r"\textbf{Fake Startup} \hfill CTO \\" + "\n"
    )
    ok, violations = check_identity(injected, ledger)
    assert ok is False
    assert violations
    assert any("extra" in v.lower() or "role" in v.lower() for v in violations)
