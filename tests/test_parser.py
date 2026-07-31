"""Tests for src.agents.parser - resume parsing + ledger derivation.

`parse_fast` is mocked: NO live API calls. The mock returns a fixed
``ResumeStruct`` so we can assert the node's derivation logic in isolation.
"""
import logging

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


def test_parse_resume_logs_the_actual_model_context_override(monkeypatch, caplog):
    """Regression test: the log line used to hardcode MODEL_FAST from
    config.settings, so it lied whenever a per-job model_context override was
    active. It must report the override, not the static settings constant."""
    from src.pipeline.llm import model_context

    monkeypatch.setattr(parser, "parse_fast", lambda *a, **k: _fixed_struct())

    with caplog.at_level(logging.INFO, logger="src.agents.parser"):
        with model_context(
            fast="google/gemini-2.5-flash-lite", strong="s", temp_fast=0.0
        ):
            parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})

    log_text = " ".join(caplog.messages)
    assert "google/gemini-2.5-flash-lite" in log_text
    assert "temp=0.0" in log_text


def test_parse_resume_does_not_mutate_input_state(monkeypatch):
    """Immutability: the incoming state dict is not mutated."""
    monkeypatch.setattr(parser, "parse_fast", lambda *a, **k: _fixed_struct())
    state = {"resume_tex_raw": SAMPLE_TEX}
    parser.parse_resume(state)
    assert state == {"resume_tex_raw": SAMPLE_TEX}


def test_parse_resume_skips_llm_call_when_cached(monkeypatch):
    """When resume_struct + identity_ledger are already in state (seeded by a
    caller that parsed this resume once - e.g. a batch run reusing the parse
    across multiple JDs), parse_resume must NOT call parse_fast and must
    return the cached pair unchanged."""
    called = {"n": 0}

    def fake_parse_fast(*a, **k):
        called["n"] += 1
        return _fixed_struct()

    monkeypatch.setattr(parser, "parse_fast", fake_parse_fast)

    struct = _fixed_struct()
    ledger = _ledger_from_struct(struct)
    state = {
        "resume_tex_raw": SAMPLE_TEX,
        "resume_struct": struct,
        "identity_ledger": ledger,
    }

    out = parser.parse_resume(state)

    assert called["n"] == 0, "parse_fast must not be called when a cached struct/ledger is present"
    assert out == {"resume_struct": struct, "identity_ledger": ledger}
    assert out["resume_struct"] is struct
    assert out["identity_ledger"] is ledger


def test_parse_resume_cache_requires_both_fields(monkeypatch):
    """A partially-seeded state (only one of the two cached fields) must still
    parse via the LLM - the cache short-circuit only fires when BOTH are present."""
    struct = _fixed_struct()
    captured = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured["called"] = True
        return _fixed_struct()

    monkeypatch.setattr(parser, "parse_fast", fake_parse_fast)

    state = {"resume_tex_raw": SAMPLE_TEX, "resume_struct": struct}
    parser.parse_resume(state)

    assert captured.get("called") is True


def test_parse_resume_cache_miss_stores_payload_then_hits_on_next_call(monkeypatch):
    """First call with no state-seed and an empty hash cache is a MISS: it calls
    the LLM and stores the result. A second call with the identical resume text
    (fresh state, no seeding) is a HIT: it must NOT call the LLM again, and must
    return a byte-identical resume_struct/identity_ledger to the first call."""
    from src.db.parse_cache import InMemoryResumeParseCacheRepository

    called = {"n": 0}

    def fake_parse_fast(system, user, schema, **kwargs):
        called["n"] += 1
        return _fixed_struct()

    monkeypatch.setattr(parser, "parse_fast", fake_parse_fast)
    # Single repo instance shared across both calls, like a real persistent cache.
    repo = InMemoryResumeParseCacheRepository()
    monkeypatch.setattr(parser, "get_parse_cache_repo", lambda: repo)

    first = parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})
    assert called["n"] == 1

    second = parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})
    assert called["n"] == 1, "cache HIT must not re-invoke the LLM"

    assert second["resume_struct"] == first["resume_struct"]
    assert second["identity_ledger"] == first["identity_ledger"]


def test_parse_resume_cache_hit_logs_and_miss_stores(monkeypatch, caplog):
    """Logging contract: MISS logs the existing 'sending N chars' line plus a
    new 'cache MISS - stored' line; HIT logs 'cache HIT ... skipping LLM call'
    and never logs the 'sending N chars' line."""
    from src.db.parse_cache import InMemoryResumeParseCacheRepository

    monkeypatch.setattr(parser, "parse_fast", lambda *a, **k: _fixed_struct())
    repo = InMemoryResumeParseCacheRepository()
    monkeypatch.setattr(parser, "get_parse_cache_repo", lambda: repo)

    with caplog.at_level(logging.INFO, logger="src.agents.parser"):
        parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})
    miss_text = " ".join(caplog.messages)
    assert "sending" in miss_text and "chars" in miss_text
    assert "cache MISS - stored" in miss_text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="src.agents.parser"):
        parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})
    hit_text = " ".join(caplog.messages)
    assert "cache HIT" in hit_text and "skipping LLM call" in hit_text
    assert "sending" not in hit_text


def test_parse_resume_cache_never_returns_payload_for_different_resume(monkeypatch):
    """A cache HIT for one resume must never leak into a request for a
    different resume (different hash) - each must call the LLM independently."""
    from src.db.parse_cache import InMemoryResumeParseCacheRepository

    called = {"n": 0}

    def fake_parse_fast(*a, **k):
        called["n"] += 1
        return _fixed_struct()

    monkeypatch.setattr(parser, "parse_fast", fake_parse_fast)
    repo = InMemoryResumeParseCacheRepository()
    monkeypatch.setattr(parser, "get_parse_cache_repo", lambda: repo)

    other_tex = SAMPLE_TEX + "\n% a trailing comment that changes the hash\n"

    parser.parse_resume({"resume_tex_raw": SAMPLE_TEX})
    parser.parse_resume({"resume_tex_raw": other_tex})

    assert called["n"] == 2


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


# --- extract_name: preamble must not poison the identity (Step 1 fix) ----------

# A realistic resume whose preamble binds a font named "XCharter". The OLD
# extract_name grabbed the FIRST \command{...} anywhere in the raw tex, so it
# returned "XCharter" (or "article" from \documentclass) instead of the human
# name. The name lives in the \begin{document} body, wrapped in formatting.
PREAMBLE_TEX = r"""
\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{XCharter}
\setmainfont{XCharter}
\newcommand{\name}[1]{\textbf{#1}}
\definecolor{accent}{HTML}{1A1A1A}
\begin{document}
\begin{center}
{\Large \textbf{Grace Hopper}} \\
grace.hopper@example.com $\cdot$ (555) 000-1111
\end{center}

\section*{Experience}
\textbf{US Navy} \hfill 1944 -- 1966 \\
\textit{Rear Admiral}
\end{document}
"""


def test_extract_name_ignores_preamble_font_package():
    """The name comes from the document body, NOT a \\usepackage/font argument."""
    name = parser.extract_name(PREAMBLE_TEX)
    assert name == "Grace Hopper"
    assert name != "XCharter"


def test_extract_name_ignores_documentclass_argument():
    """\\documentclass{article} must never be mistaken for the candidate name."""
    assert parser.extract_name(SAMPLE_TEX) == "Jane Doe"


def test_extract_name_skips_structural_begin_center():
    """A leading \\begin{center} wrapper must be skipped, not read as 'center'."""
    name = parser.extract_name(PREAMBLE_TEX)
    assert name != "center"


def test_extract_name_strips_preamble_without_document_env():
    """No \\begin{document}: preamble command lines are stripped before search."""
    tex = "\\usepackage{XCharter}\n\\textbf{Ada Lovelace}\nada@example.com"
    assert parser.extract_name(tex) == "Ada Lovelace"
