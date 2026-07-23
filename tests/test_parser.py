"""Tests for src.agents.parser — resume parsing + ledger derivation.

`parse_fast` is mocked: NO live API calls. The mock returns a fixed
``ResumeStruct`` so we can assert the node's derivation logic in isolation.
"""
import pytest

from src.agents import parser
from src.pipeline.schemas import IdentityLedger, ResumeRole, ResumeStruct

SAMPLE_TEX = r"""
\documentclass{article}
\begin{document}
\textbf{Jane Doe} \\
jane.doe@example.com $\cdot$ (555) 123-4567

\section*{Experience}
\textbf{Acme Corp} \hfill Jan 2021 -- Present \\
\textit{Senior Data Engineer}
\begin{itemize}
  \item Built REST-based CRM-sync ETL job moving 2M customer records/day.
  \item Reduced pipeline latency 40\% via incremental extraction.
\end{itemize}

\textbf{Beta Labs} \hfill Jun 2018 -- Dec 2020 \\
\textit{Software Engineer}
\begin{itemize}
  \item Designed internal data mapping service across 6 systems.
\end{itemize}
\end{document}
"""


def _fixed_struct() -> ResumeStruct:
    return ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp",
                title="Senior Data Engineer",
                start="Jan 2021",
                end="Present",
                source_evidence=[
                    "Built REST-based CRM-sync ETL job moving 2M customer records/day.",
                    "Reduced pipeline latency 40\\% via incremental extraction.",
                ],
            ),
            ResumeRole(
                company="Beta Labs",
                title="Software Engineer",
                start="Jun 2018",
                end="Dec 2020",
                source_evidence=[
                    "Designed internal data mapping service across 6 systems.",
                ],
            ),
        ],
        education=["BS Computer Science, State University, 2018"],
        skills=["Python", "SQL", "Airflow", "REST APIs"],
    )


def test_parse_resume_writes_struct_and_ledger(monkeypatch):
    """parse_resume returns both resume_struct and a derived identity_ledger."""
    struct = _fixed_struct()
    captured = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        return struct

    monkeypatch.setattr(parser, "parse_fast", fake_parse_fast)

    state = {"resume_tex_raw": SAMPLE_TEX}
    out = parser.parse_resume(state)

    # Node called parse_fast with the raw tex and the ResumeStruct schema.
    assert captured["schema"] is ResumeStruct
    assert captured["user"] == SAMPLE_TEX
    assert isinstance(captured["system"], str) and captured["system"]

    # Node returns a NEW dict with exactly the extraction outputs.
    assert set(out.keys()) == {"resume_struct", "identity_ledger"}
    assert out["resume_struct"] is struct

    ledger = out["identity_ledger"]
    assert isinstance(ledger, IdentityLedger)
    # Identity fields are copied character-exact from the struct into the ledger.
    assert [r.company for r in ledger.roles] == ["Acme Corp", "Beta Labs"]
    assert ledger.roles[0].title == "Senior Data Engineer"
    assert ledger.roles[0].start == "Jan 2021"
    assert ledger.roles[0].end == "Present"


def test_parse_resume_does_not_mutate_input_state(monkeypatch):
    """Immutability: the incoming state dict is not mutated."""
    monkeypatch.setattr(parser, "parse_fast", lambda *a, **k: _fixed_struct())
    state = {"resume_tex_raw": SAMPLE_TEX}
    parser.parse_resume(state)
    assert state == {"resume_tex_raw": SAMPLE_TEX}


def _ledger_from_struct(struct: ResumeStruct) -> IdentityLedger:
    return parser.derive_ledger(struct, name="Jane Doe", contact="jane.doe@example.com")


def test_assert_ledger_matches_source_passes_when_verbatim():
    """Guard passes when every identity substring appears verbatim in raw tex."""
    ledger = _ledger_from_struct(_fixed_struct())
    # Should not raise.
    parser.assert_ledger_matches_source(ledger, SAMPLE_TEX)


def test_assert_ledger_matches_source_raises_on_company_drift():
    """Guard raises when a company was paraphrased/altered vs the source."""
    struct = _fixed_struct()
    drifted = struct.roles[0].model_copy(update={"company": "ACME Corporation"})
    struct = struct.model_copy(update={"roles": [drifted, struct.roles[1]]})
    ledger = _ledger_from_struct(struct)

    with pytest.raises(ValueError) as exc:
        parser.assert_ledger_matches_source(ledger, SAMPLE_TEX)
    assert "company" in str(exc.value)
    assert "ACME Corporation" in str(exc.value)


def test_assert_ledger_matches_source_raises_on_date_drift():
    """Guard raises when a date was reformatted vs the source."""
    struct = _fixed_struct()
    drifted = struct.roles[0].model_copy(update={"start": "January 2021"})
    struct = struct.model_copy(update={"roles": [drifted, struct.roles[1]]})
    ledger = _ledger_from_struct(struct)

    with pytest.raises(ValueError) as exc:
        parser.assert_ledger_matches_source(ledger, SAMPLE_TEX)
    assert "start" in str(exc.value)
