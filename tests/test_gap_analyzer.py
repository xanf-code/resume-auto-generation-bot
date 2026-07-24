"""Tests for src.agents.gap_analyzer — reframing-target extraction node.

`parse_gap` is mocked to return a ``GapTargets`` wrapper holding a mix of a
reframable target (real evidence) and a no-evidence target. NO live API calls.
The node must unwrap the wrapper into a plain list under ``gap_targets`` and
must PRESERVE the no_evidence target (it is reported later, not dropped).
"""
import logging

from src.agents import gap_analyzer
from src.pipeline.schemas import (
    GapTargets,
    JDVector,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    SkillWeight,
)


def _resume_struct() -> ResumeStruct:
    return ResumeStruct(
        roles=[
            ResumeRole(
                company="Acme Corp",
                title="Senior Data Engineer",
                start="Jan 2021",
                end="Present",
                source_evidence=[
                    "Built REST-based CRM-sync ETL job moving 2M customer records/day.",
                ],
            ),
        ],
        education=["BS Computer Science, State University, 2018"],
        skills=["Python", "SQL", "REST APIs"],
    )


def _jd_vector() -> JDVector:
    return JDVector(
        weighted_skills=[
            SkillWeight(name="Salesforce", weight=0.95),
            SkillWeight(name="Kubernetes", weight=0.6),
        ],
        ats_keywords=["Salesforce", "CRM", "Kubernetes"],
        seniority="senior",
        must_mirror=["Salesforce/CRM data sync"],
    )


def _wrapper() -> GapTargets:
    reframable = ReframingTarget(
        competency="Salesforce",
        weight=0.95,
        host_role_index=0,
        real_evidence=[
            "Built REST-based CRM-sync ETL job moving 2M customer records/day.",
        ],
        framing_guidance=(
            "Frame the CRM-sync ETL job as REST-based data integration that "
            "syncs customer records into a CRM platform — surfacing "
            "Salesforce-adjacent competency (API integration, data mapping)."
        ),
        no_evidence=False,
    )
    absent = ReframingTarget(
        competency="Kubernetes",
        weight=0.6,
        host_role_index=-1,
        real_evidence=[],
        framing_guidance="",
        no_evidence=True,
    )
    return GapTargets(targets=[reframable, absent])


def test_gap_analysis_writes_unwrapped_list(monkeypatch):
    wrapper = _wrapper()
    captured = {}

    def fake_parse_gap(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        return wrapper

    monkeypatch.setattr(gap_analyzer, "parse_gap", fake_parse_gap)

    state = {"resume_struct": _resume_struct(), "jd_vector": _jd_vector()}
    out = gap_analyzer.gap_analysis(state)

    # parse_gap was asked to fill the wrapper model, not a bare list.
    assert captured["schema"] is GapTargets
    assert isinstance(captured["system"], str) and captured["system"]
    # The user message combines both resume + JD context.
    assert "Salesforce" in captured["user"]
    assert "CRM-sync ETL" in captured["user"]

    # Output is the plain list, unwrapped from the GapTargets wrapper.
    assert set(out.keys()) == {"gap_targets"}
    targets = out["gap_targets"]
    assert isinstance(targets, list)
    assert all(isinstance(t, ReframingTarget) for t in targets)
    assert len(targets) == 2


def test_gap_analysis_preserves_no_evidence_target(monkeypatch):
    """The no_evidence target must survive to state (reported later, not dropped)."""
    monkeypatch.setattr(gap_analyzer, "parse_gap", lambda *a, **k: _wrapper())
    out = gap_analyzer.gap_analysis(
        {"resume_struct": _resume_struct(), "jd_vector": _jd_vector()}
    )
    targets = out["gap_targets"]

    no_ev = [t for t in targets if t.no_evidence]
    assert len(no_ev) == 1
    assert no_ev[0].competency == "Kubernetes"


def test_gap_analysis_reframable_target_has_real_evidence(monkeypatch):
    """The reframable target cites non-empty real evidence strings."""
    monkeypatch.setattr(gap_analyzer, "parse_gap", lambda *a, **k: _wrapper())
    out = gap_analyzer.gap_analysis(
        {"resume_struct": _resume_struct(), "jd_vector": _jd_vector()}
    )
    targets = out["gap_targets"]

    reframable = [t for t in targets if not t.no_evidence]
    assert len(reframable) == 1
    assert reframable[0].real_evidence
    assert all(e.strip() for e in reframable[0].real_evidence)
    assert reframable[0].framing_guidance.strip()


def test_gap_analysis_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(gap_analyzer, "parse_gap", lambda *a, **k: _wrapper())
    state = {"resume_struct": _resume_struct(), "jd_vector": _jd_vector()}
    snapshot_keys = set(state.keys())
    gap_analyzer.gap_analysis(state)
    assert set(state.keys()) == snapshot_keys


def test_gap_analysis_logs_fabrication_targets(monkeypatch, caplog):
    """Active fabrication targets and skipped no-evidence gaps both appear in logs."""
    monkeypatch.setattr(gap_analyzer, "parse_gap", lambda *a, **k: _wrapper())
    with caplog.at_level(logging.INFO, logger="src.agents.gap_analyzer"):
        gap_analyzer.gap_analysis(
            {"resume_struct": _resume_struct(), "jd_vector": _jd_vector()}
        )
    log_text = " ".join(caplog.messages)
    # Active fabrication target is named
    assert "Salesforce" in log_text
    assert "fabricat" in log_text.lower()
    # No-evidence gap is called out as skipped
    assert "Kubernetes" in log_text
    assert "no evidence" in log_text.lower() or "not fabricated" in log_text.lower()
