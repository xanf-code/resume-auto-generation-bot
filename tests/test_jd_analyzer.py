"""Tests for src.agents.jd_analyzer - JD -> JDVector node.

`parse_fast` is mocked to return a fixed ``JDVector``; NO live API calls.
"""
import logging

from src.agents import jd_analyzer
from src.agents.jd_tagger import JdClassification
from src.pipeline.schemas import JDVector, SkillWeight

SAMPLE_JD = (
    "Senior Data Engineer. Own Salesforce/CRM data sync, build REST APIs and "
    "ETL pipelines. Must have 5+ years experience."
)


def _fixed_vector() -> JDVector:
    return JDVector(
        weighted_skills=[
            SkillWeight(name="Salesforce", weight=0.95),
            SkillWeight(name="REST APIs", weight=0.9),
            SkillWeight(name="ETL pipelines", weight=0.85),
        ],
        ats_keywords=["Salesforce", "CRM", "REST APIs", "ETL pipelines"],
        seniority="senior",
        must_mirror=["Salesforce/CRM data sync", "REST APIs", "ETL pipelines"],
    )


def test_analyze_jd_writes_jd_vector(monkeypatch):
    vector = _fixed_vector()
    captured = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        return vector

    monkeypatch.setattr(jd_analyzer, "parse_fast", fake_parse_fast)
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type", lambda jd_raw: JdClassification(role=None, domains=[])
    )

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    assert captured["schema"] is JDVector
    assert captured["user"] == SAMPLE_JD
    assert isinstance(captured["system"], str) and captured["system"]

    assert set(out.keys()) == {"jd_vector", "jd_domains"}
    assert out["jd_vector"] is vector


def test_analyze_jd_writes_jd_domains_from_tagger(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer,
        "classify_jd_type",
        lambda jd_raw: JdClassification(role="data", domains=["data-platform", "saas"]),
    )

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    assert out["jd_domains"] == ["data-platform", "saas"]


def test_analyze_jd_jd_domains_empty_when_tagger_finds_none(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type", lambda jd_raw: JdClassification(role=None, domains=[])
    )

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    assert out["jd_domains"] == []


def test_analyze_jd_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type", lambda jd_raw: JdClassification(role=None, domains=[])
    )
    state = {"jd_raw": SAMPLE_JD}
    jd_analyzer.analyze_jd(state)
    assert state == {"jd_raw": SAMPLE_JD}


def test_analyze_jd_logs_the_actual_model_context_override(monkeypatch, caplog):
    """Regression test: the log line used to hardcode MODEL_FAST from
    config.settings, so it lied whenever a per-job model_context override was
    active. It must report the override, not the static settings constant."""
    from src.pipeline.llm import model_context

    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type", lambda jd_raw: JdClassification(role=None, domains=[])
    )
    with caplog.at_level(logging.INFO, logger="src.agents.jd_analyzer"):
        with model_context(
            fast="google/gemini-2.5-flash-lite", strong="s", extra_fast={"temperature": 0.0}
        ):
            jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    log_text = " ".join(caplog.messages)
    assert "google/gemini-2.5-flash-lite" in log_text
    assert "temperature': 0.0" in log_text


# --- reusing a seeded jd_domains classification (avoids a redundant call) ------
#
# The web path (src/web/runner.py) classifies the JD once, inside its own
# model_context, before the graph even starts (it needs the role/domains split
# to resolve vault retrieval and tuning overrides). It hands that result down
# via stream_pipeline's jd_domains kwarg. analyze_jd must reuse it verbatim
# instead of calling classify_jd_type a second, independent time - which used
# to run on whatever model this node's own model_context resolved parse_fast
# to, a call that could disagree with the first one since they're independent
# LLM calls. CLI callers (which never seed jd_domains) are unaffected - this
# node still classifies for them exactly as before.


def test_analyze_jd_reuses_seeded_jd_domains_without_calling_tagger(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())

    def fail_if_called(jd_raw):
        raise AssertionError("classify_jd_type must not be called when jd_domains is seeded")

    monkeypatch.setattr(jd_analyzer, "classify_jd_type", fail_if_called)

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD, "jd_domains": ["fintech", "ai"]})

    assert out["jd_domains"] == ["fintech", "ai"]


def test_analyze_jd_reuses_seeded_empty_jd_domains_without_calling_tagger(monkeypatch):
    """An explicit empty list is still a seeded value (JD tagged no domains) -
    distinct from the key being absent entirely."""
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())

    def fail_if_called(jd_raw):
        raise AssertionError("classify_jd_type must not be called when jd_domains is seeded")

    monkeypatch.setattr(jd_analyzer, "classify_jd_type", fail_if_called)

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD, "jd_domains": []})

    assert out["jd_domains"] == []


def test_analyze_jd_computes_jd_domains_when_not_seeded(monkeypatch):
    """CLI path (or any caller that doesn't pre-seed jd_domains) is unaffected -
    the tagger still runs exactly as before."""
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type",
        lambda jd_raw: JdClassification(role="data", domains=["data-platform"]),
    )

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    assert out["jd_domains"] == ["data-platform"]


def test_analyze_jd_logs_when_reusing_seeded_jd_domains(monkeypatch, caplog):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer,
        "classify_jd_type",
        lambda jd_raw: (_ for _ in ()).throw(AssertionError("must not be called")),
    )

    with caplog.at_level(logging.INFO, logger="src.agents.jd_analyzer"):
        jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD, "jd_domains": ["fintech"]})

    log_text = " ".join(caplog.messages)
    assert "seeded" in log_text.lower()
    assert "skipping" in log_text.lower()


def test_analyze_jd_logs_extracted_keywords(monkeypatch, caplog):
    """Extracted ATS keywords, weighted skills, and must-mirror phrases appear in logs."""
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    monkeypatch.setattr(
        jd_analyzer, "classify_jd_type", lambda jd_raw: JdClassification(role=None, domains=[])
    )
    with caplog.at_level(logging.INFO, logger="src.agents.jd_analyzer"):
        jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})
    log_text = " ".join(caplog.messages)
    # ATS keywords logged
    assert "Salesforce" in log_text
    assert "REST APIs" in log_text
    assert "ETL pipelines" in log_text
    # weighted skills logged with weights
    assert "0.95" in log_text
    assert "0.90" in log_text or "0.9" in log_text
    # must-mirror surfaced
    assert "Salesforce/CRM data sync" in log_text
