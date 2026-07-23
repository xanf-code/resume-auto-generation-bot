"""Tests for src.agents.jd_analyzer — JD -> JDVector node.

`parse_fast` is mocked to return a fixed ``JDVector``; NO live API calls.
"""
from src.agents import jd_analyzer
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

    out = jd_analyzer.analyze_jd({"jd_raw": SAMPLE_JD})

    assert captured["schema"] is JDVector
    assert captured["user"] == SAMPLE_JD
    assert isinstance(captured["system"], str) and captured["system"]

    assert set(out.keys()) == {"jd_vector"}
    assert out["jd_vector"] is vector


def test_analyze_jd_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "parse_fast", lambda *a, **k: _fixed_vector())
    state = {"jd_raw": SAMPLE_JD}
    jd_analyzer.analyze_jd(state)
    assert state == {"jd_raw": SAMPLE_JD}
