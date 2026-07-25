"""Tests for src.agents.writer - the Writer (Opus) node and its user-message builder.

``parse_strong`` is mocked to return a canned ``WriterOutput``; NO live API calls
(ANTHROPIC_API_KEY is intentionally unset). These tests pin the DETERMINISTIC
message-construction behaviour - the core of the Writer's testable surface - plus
the node's contract: it writes ``writer_output`` and never mutates input state.
"""
import logging

from config.settings import EFFORT_STRONG
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
    state["revision_notes"] = ["Strengthen the impact verb on the CRM bullet."]

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
    state["revision_notes"] = ["Tighten the opening bullet."]

    msg = writer.build_writer_user_message(state)

    assert "REVISION NOTES" in msg
    assert "Tighten the opening bullet" in msg


def test_different_revision_notes_produce_different_messages():
    """Feeding different revision_notes visibly changes the next draft's prompt."""
    base = _first_iteration_state()
    base["iteration"] = 2
    base["writer_output"] = _writer_output()

    state_a = {**base, "revision_notes": ["Add a quantified metric to bullet 1."]}
    state_b = {**base, "revision_notes": ["Remove jargon from bullet 2."]}

    msg_a = writer.build_writer_user_message(state_a)
    msg_b = writer.build_writer_user_message(state_b)

    assert msg_a != msg_b
    assert "Add a quantified metric to bullet 1" in msg_a
    assert "Remove jargon from bullet 2" in msg_b


# --- build_writer_user_message: compile bounce ---------------------------------


def test_compile_errors_include_compile_section():
    """compile_errors present => the compile-error section appears."""
    state = _first_iteration_state()
    state["writer_output"] = _writer_output()
    state["compile_errors"] = "Undefined control sequence \\emoji on line 42."

    msg = writer.build_writer_user_message(state)

    assert "COMPILE ERRORS" in msg
    assert "Undefined control sequence" in msg


# --- build_writer_user_message: identity violations ----------------------------


def test_build_writer_user_message_includes_violations():
    """identity_violations present => IDENTITY VIOLATIONS section appears."""
    state = _first_iteration_state()
    state["identity_violations"] = [
        "role[0].company = 'Acme Corp' not found verbatim in rendered LaTeX.",
    ]
    msg = writer.build_writer_user_message(state)

    assert "IDENTITY VIOLATIONS" in msg
    assert "Acme Corp" in msg


def test_build_writer_user_message_no_violations_section_when_empty():
    """Empty identity_violations list → no IDENTITY VIOLATIONS section."""
    state = _first_iteration_state()
    state["identity_violations"] = []
    msg = writer.build_writer_user_message(state)

    assert "IDENTITY VIOLATIONS" not in msg


def test_build_writer_user_message_no_violations_section_when_absent():
    """Absent identity_violations key → no IDENTITY VIOLATIONS section."""
    msg = writer.build_writer_user_message(_first_iteration_state())

    assert "IDENTITY VIOLATIONS" not in msg


# --- build_writer_user_message: length violations ------------------------------


def test_build_writer_user_message_includes_length_violations():
    """length_violations present → LENGTH VIOLATIONS section appears."""
    state = _first_iteration_state()
    state["writer_output"] = _writer_output()
    state["length_violations"] = [
        "Role 0 bullet 0: 142 chars (UNDERBUILT by 53). Target: 195-210 chars.",
        "Role 0 bullet 1: 230 chars (BLOATED by 20). Target: 195-210 chars.",
    ]
    msg = writer.build_writer_user_message(state)

    assert "LENGTH VIOLATIONS" in msg
    assert "Role 0 bullet 0: 142 chars" in msg
    assert "Role 0 bullet 1: 230 chars" in msg
    assert "fix ONLY these bullets to 195-210 chars" in msg


def test_build_writer_user_message_no_length_violations_when_empty():
    """Empty length_violations list → no LENGTH VIOLATIONS section."""
    state = _first_iteration_state()
    state["length_violations"] = []
    msg = writer.build_writer_user_message(state)

    assert "LENGTH VIOLATIONS" not in msg


def test_build_writer_user_message_no_length_violations_when_absent():
    """Absent length_violations key → no LENGTH VIOLATIONS section."""
    msg = writer.build_writer_user_message(_first_iteration_state())

    assert "LENGTH VIOLATIONS" not in msg


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

    # It parsed against WriterOutput on the strong model.
    assert captured["schema"] is WriterOutput
    # Effort is NOT passed at the call site - it defers to parse_strong's
    # own default (config.settings.EFFORT_STRONG), so retuning reasoning
    # depth only requires a settings change, not a writer.py edit.
    assert "effort" not in captured["kwargs"]
    # The system prompt is the Writer's hard-rules prompt.
    assert isinstance(captured["system"], str) and captured["system"]


def test_write_resume_logs_configured_effort(monkeypatch, caplog):
    """The log line reports the ACTUAL configured effort from settings, not a
    hardcoded literal - so log output stays truthful if EFFORT_STRONG changes."""
    monkeypatch.setattr(writer, "parse_strong", lambda *a, **k: _writer_output())

    with caplog.at_level(logging.INFO, logger="src.agents.writer"):
        writer.write_resume(_first_iteration_state())

    log_text = " ".join(caplog.messages)
    assert f"effort={EFFORT_STRONG}" in log_text


def test_write_resume_strips_char_annotations(monkeypatch):
    """The [chars: N] self-verification tags must NEVER reach the output.

    The Writer prompt asks the model to append ``[chars: N]`` to each bullet so
    it can self-check length. Those tags are for the model only - they must be
    stripped before the validator counts chars and before the renderer injects
    the bullet into the PDF.
    """
    annotated = WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "Built an ETL pipeline in Python that cut reporting time. [chars: 202]",
                    "Scaled the service to 8M+ users on the platform [chars: 199]",
                ],
            ),
        ],
    )
    monkeypatch.setattr(writer, "parse_strong", lambda *a, **k: annotated)

    out = writer.write_resume(_first_iteration_state())
    bullets = [b for role in out["writer_output"].roles for b in role.bullets]

    assert all("[chars:" not in b for b in bullets)
    assert bullets[0] == "Built an ETL pipeline in Python that cut reporting time."
    assert bullets[1] == "Scaled the service to 8M+ users on the platform"


def test_write_resume_leaves_clean_bullets_untouched(monkeypatch):
    """Bullets with no annotation pass through unchanged (same object identity)."""
    canned = _writer_output()  # no [chars: N] tags
    monkeypatch.setattr(writer, "parse_strong", lambda *a, **k: canned)

    out = writer.write_resume(_first_iteration_state())
    assert out["writer_output"] is canned


def test_write_resume_does_not_mutate_input_state(monkeypatch):
    monkeypatch.setattr(writer, "parse_strong", lambda *a, **k: _writer_output())

    state = _first_iteration_state()
    snapshot_keys = set(state.keys())
    writer.write_resume(state)

    assert set(state.keys()) == snapshot_keys
    assert "writer_output" not in state


def test_writer_system_enforces_keyword_coverage_cap():
    """WRITER_SYSTEM must cap keyword coverage at 80-85% to prevent stuffing signals."""
    from src.prompts.writer import WRITER_SYSTEM

    assert "80-85" in WRITER_SYSTEM, "Missing 80-85% keyword coverage cap"
    assert "stuffing" in WRITER_SYSTEM.lower(), "Missing stuffing-signal warning"
    # Must still require 100% coverage of must_mirror and high-weight skills
    assert "must_mirror" in WRITER_SYSTEM
    assert "0.8" in WRITER_SYSTEM


def test_writer_system_enforces_bullet_band():
    """Bullet band is the required 195-210 (min 195, max 210)."""
    from src.prompts.writer import WRITER_SYSTEM

    assert "195-210" in WRITER_SYSTEM, "Missing 195-210 bullet band"


def test_writer_system_caps_bullet_count_flexibly():
    """8 bullets total, hard-max 5 per role, relevance-driven split."""
    from src.prompts.writer import WRITER_SYSTEM

    assert "8 bullets total" in WRITER_SYSTEM
    assert "5 per role" in WRITER_SYSTEM
    # The old rigid 4-per-role cap must be gone.
    assert "maximum 4 bullets per role" not in WRITER_SYSTEM


def test_writer_system_does_not_mention_summary():
    """Summary is removed from the app - the Writer must not emit one."""
    from src.prompts.writer import WRITER_SYSTEM

    assert "summary" not in WRITER_SYSTEM.lower()


# --- build_writer_user_message: BULLET SHAPE DIRECTIVE section ----------------


def test_build_writer_user_message_always_includes_bullet_shape_directive():
    """Every call to build_writer_user_message must include the shape directive header."""
    msg = writer.build_writer_user_message(_first_iteration_state())
    assert "## BULLET SHAPE DIRECTIVE" in msg


def test_build_writer_user_message_default_state_has_rotation_text():
    """No bullet_shapes in state → full rotation directive text."""
    msg = writer.build_writer_user_message(_first_iteration_state())
    # Full rotation directive should include all four shape names
    for name in ("PAR", "RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"):
        assert name in msg, f"Shape {name!r} missing from default-state message"


def test_build_writer_user_message_single_shape_has_only():
    """bullet_shapes=["PAR"] → USE ONLY PAR language in the message."""
    state = _first_iteration_state()
    state["bullet_shapes"] = ["PAR"]
    msg = writer.build_writer_user_message(state)
    assert "USE ONLY PAR" in msg
    assert "## BULLET SHAPE DIRECTIVE" in msg


def test_build_writer_user_message_bullet_shape_directive_precedes_resume():
    """The BULLET SHAPE DIRECTIVE section appears before the RESUME section."""
    msg = writer.build_writer_user_message(_first_iteration_state())
    directive_pos = msg.index("## BULLET SHAPE DIRECTIVE")
    resume_pos = msg.index("## RESUME")
    assert directive_pos < resume_pos


def test_build_writer_user_message_subset_shapes_rotates_among():
    """bullet_shapes subset → 'Rotate ONLY among' language."""
    state = _first_iteration_state()
    state["bullet_shapes"] = ["PAR", "RESULT-FIRST"]
    msg = writer.build_writer_user_message(state)
    assert "Rotate ONLY among" in msg
    assert "## BULLET SHAPE DIRECTIVE" in msg
