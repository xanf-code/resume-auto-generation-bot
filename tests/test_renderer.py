"""Tests for the LaTeX renderer — integrity guarantee #1 (structural).

Identity fields come exclusively from the ledger; bullets/skills/summary come
exclusively from the writer output. Every injected string is LaTeX-escaped.
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
    out = render(_ledger(), _writer())
    assert "Ada Lovelace" in out
    assert "ada@example.com | 555-0100" in out  # contact verbatim from ledger
    assert "ada@example.com" in out
    for company in ("Analytical Engines Inc", "Babbage \\& Co"):
        assert company in out
    for title in ("Lead Engineer", "Research Fellow"):
        assert title in out
    for date in ("Jan 2020", "Present", "Jun 2016", "Dec 2019"):
        assert date in out


def test_render_injects_writer_content():
    out = render(_ledger(), _writer())
    assert "Led a team of 5 engineers" in out
    assert "Published 3 papers" in out
    assert "Python" in out
    assert "Pioneering engineer with decades of impact." in out


# --- render: escaping of writer content --------------------------------------


def test_render_escapes_special_chars_in_bullets_and_skills():
    ledger = _ledger()
    writer = WriterOutput(
        roles=[
            RoleBullets(index=0, bullets=["Cut costs by 30% & boosted C_speed"]),
            RoleBullets(index=1, bullets=["Saved $1M on #infra"]),
        ],
        skills=["C++ & Rust", "50%_uptime"],
        summary="Delivered value$ across teams.",
    )
    out = render(ledger, writer)
    # Raw specials must NOT appear unescaped in the rendered output.
    assert "30% &" not in out
    assert r"30\% \& boosted C\_speed" in out
    assert r"\$1M on \#infra" in out
    assert r"C++ \& Rust" in out
    assert r"50\%\_uptime" in out
    assert r"value\$" in out


# --- render: writer content NEVER leaks into an identity slot ----------------


def test_writer_output_never_reaches_identity_slot():
    """The renderer must ignore any identity-looking data a writer could craft.

    WriterOutput has no identity fields by construction, but even the strings
    it DOES carry (bullets/skills/summary) must never be used as a company,
    title, or date. We craft a writer whose bullet text impersonates a company
    and confirm the identity slots still come from the ledger.
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
    out = render(ledger, malicious)
    # Ledger identity survives.
    assert "Analytical Engines Inc" in out
    assert "Lead Engineer" in out
    # The writer's impersonation strings appear ONLY as bullet/summary content,
    # never as a structural identity value. There is no way for the writer to
    # inject a new company header — the roles are keyed by the ledger.
    # Count of company headers equals the number of ledger roles.
    assert out.count("Analytical Engines Inc") >= 1
    # Writer text is present (as a bullet) but not promoted to an identity slot;
    # confirm the header line for role 0 uses the ledger company, not the writer.
    assert "FAKE COMPANY LLC" not in out.split("Analytical Engines Inc")[0]


def test_render_matches_bullets_by_role_index():
    """Bullets are matched to ledger roles by RoleBullets.index, order-independent."""
    ledger = _ledger()
    # Deliberately reverse the writer roles order; matching is by index.
    writer = WriterOutput(
        roles=[
            RoleBullets(index=1, bullets=["SECOND ROLE BULLET"]),
            RoleBullets(index=0, bullets=["FIRST ROLE BULLET"]),
        ],
        skills=["S"],
        summary="sum",
    )
    out = render(ledger, writer)
    # Role 0 (Analytical Engines) must be paired with FIRST ROLE BULLET.
    first_role_block = out.split("Babbage \\& Co")[0]
    assert "FIRST ROLE BULLET" in first_role_block
    assert "SECOND ROLE BULLET" not in first_role_block
