"""Tests for src.agents.writer — the Writer (Opus) node and its user-message builder.

``parse_strong`` is mocked to return a canned ``WriterOutput``; NO live API calls
(ANTHROPIC_API_KEY is intentionally unset). These tests pin the DETERMINISTIC
message-construction behaviour — the core of the Writer's testable surface — plus
the node's contract: it writes ``writer_output`` and never mutates input state.
"""
from src.agents import writer
from src.pipeline.schemas import (
    JDVector,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    RoleBullets,
    SkillWeight,
    WriterOutput,
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


def _gap_targets() -> list[ReframingTarget]:
    return [
        ReframingTarget(
            competency="Salesforce",
            weight=0.95,
            host_role_index=0,
            real_evidence=[
                "Built REST-based CRM-sync ETL job moving 2M customer records/day.",
            ],
            framing_guidance=(
                "Frame the CRM-sync ETL job as REST-based data integration that "
                "syncs customer records into a CRM platform."
            ),
            no_evidence=False,
        ),
    ]


def _writer_output() -> WriterOutput:
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "Integrated CRM data via REST APIs, mapping customer records "
                    "across systems.",
                ],
            ),
        ],
        skills=["Python", "SQL", "REST APIs"],
        summary="Senior data engineer specializing in REST-based data integration.",
    )


def _first_iteration_state() -> dict:
    return {
        "resume_struct": _resume_struct(),
        "jd_vector": _jd_vector(),
        "gap_targets": _gap_targets(),
    }


# --- build_writer_user_message: first iteration --------------------------------


def test_first_iteration_message_includes_core_inputs():
    """First draft: includes resume evidence, JD keywords, and framing guidance."""
    msg = writer.build_writer_user_message(_first_iteration_state())

    # resume_struct source_evidence surfaces.
    assert "CRM-sync ETL" in msg
    # jd_vector keywords surface.
    assert "Salesforce" in msg
    assert "must_mirror" in msg or "Salesforce/CRM data sync" in msg
    # gap_targets framing_guidance surfaces.
    assert "REST-based data integration that syncs customer records" in msg


def test_first_iteration_message_excludes_revision_and_compile_sections():
    """No revision_notes / compile_errors present => neither section appears."""
    msg = writer.build_writer_user_message(_first_iteration_state())

    assert "REVISION NOTES" not in msg
    assert "PRIOR DRAFT" not in msg
    assert "COMPILE ERRORS" not in msg


# --- build_writer_user_message: revision iteration -----------------------------


def test_revision_iteration_includes_prior_draft_and_notes():
    """With revision_notes + prior writer_output (iteration>=2): both appear."""
    state = _first_iteration_state()
    state["iteration"] = 2
    state["writer_output"] = _writer_output()
    state["revision_notes"] = "1. Strengthen the impact verb on the CRM bullet."

    msg = writer.build_writer_user_message(state)

    assert "REVISION NOTES" in msg
    assert "Strengthen the impact verb on the CRM bullet" in msg
    # The prior draft is surfaced so the writer can preserve good bullets.
    assert "PRIOR DRAFT" in msg
    assert "Integrated CRM data via REST APIs" in msg


def test_revision_notes_trigger_section_without_explicit_iteration():
    """revision_notes present is sufficient to include the revision section."""
    state = _first_iteration_state()
    state["writer_output"] = _writer_output()
    state["revision_notes"] = "1. Tighten the summary."

    msg = writer.build_writer_user_message(state)

    assert "REVISION NOTES" in msg
    assert "Tighten the summary" in msg


def test_different_revision_notes_produce_different_messages():
    """Feeding different revision_notes visibly changes the next draft's prompt."""
    base = _first_iteration_state()
    base["iteration"] = 2
    base["writer_output"] = _writer_output()

    state_a = {**base, "revision_notes": "1. Add a quantified metric to bullet 1."}
    state_b = {**base, "revision_notes": "1. Remove jargon from the summary."}

    msg_a = writer.build_writer_user_message(state_a)
    msg_b = writer.build_writer_user_message(state_b)

    assert msg_a != msg_b
    assert "Add a quantified metric to bullet 1" in msg_a
    assert "Remove jargon from the summary" in msg_b


# --- build_writer_user_message: compile bounce ---------------------------------


def test_compile_errors_include_compile_section():
    """compile_errors present => the compile-error section appears."""
    state = _first_iteration_state()
    state["writer_output"] = _writer_output()
    state["compile_errors"] = "Undefined control sequence \\emoji on line 42."

    msg = writer.build_writer_user_message(state)

    assert "COMPILE ERRORS" in msg
    assert "Undefined control sequence" in msg


# --- write_resume node ---------------------------------------------------------


def test_write_resume_writes_output_and_uses_correct_schema(monkeypatch):
    canned = _writer_output()
    captured = {}

    def fake_parse_strong(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        captured["kwargs"] = kwargs
        return canned

    monkeypatch.setattr(writer, "parse_strong", fake_parse_strong)

    state = _first_iteration_state()
    out = writer.write_resume(state)

    # The node writes exactly the writer_output.
    assert set(out.keys()) == {"writer_output"}
    assert out["writer_output"] is canned

    # It parsed against WriterOutput with high effort on the strong model.
    assert captured["schema"] is WriterOutput
    assert captured["kwargs"].get("effort") == "high"
    # The system prompt is the Writer's hard-rules prompt.
    assert isinstance(captured["system"], str) and captured["system"]


def test_write_resume_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(writer, "parse_strong", lambda *a, **k: _writer_output())

    state = _first_iteration_state()
    snapshot_keys = set(state.keys())
    writer.write_resume(state)

    assert set(state.keys()) == snapshot_keys
    assert "writer_output" not in state
