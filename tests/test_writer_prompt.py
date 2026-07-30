"""Phase 5 - tests for the Writer's PROVEN EXAMPLES prompt section.

``build_writer_user_message`` gains a new optional ``proven_examples`` state key
(Phase 4's retrieval output, verbatim). Present -> a ``## PROVEN EXAMPLES`` block
is appended after REFRAMING TARGETS and before REVISION/COMPILE sections. Absent
(None / key not set) -> the section is omitted entirely and the message is
byte-identical to today.
"""
from src.agents import writer
from src.pipeline.schemas import JDVector, ReframingTarget, ResumeRole, ResumeStruct, SkillWeight


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
        weighted_skills=[SkillWeight(name="Salesforce", weight=0.95)],
        ats_keywords=["Salesforce", "CRM"],
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
            framing_guidance="Frame the CRM-sync ETL job as REST-based data integration.",
            no_evidence=False,
        ),
    ]


def _base_state() -> dict:
    return {
        "resume_struct": _resume_struct(),
        "jd_vector": _jd_vector(),
        "gap_targets": _gap_targets(),
    }


_PROVEN_EXAMPLES_TEXT = (
    "## PROVEN EXAMPLES (bullets that earned interviews for similar roles - "
    "match framing/emphasis, do not invent facts)\n"
    "- Led migration of legacy billing system to microservices, cutting latency 40%."
)


def test_proven_examples_section_included_when_set():
    state = _base_state()
    state["proven_examples"] = _PROVEN_EXAMPLES_TEXT

    msg = writer.build_writer_user_message(state)

    assert "## PROVEN EXAMPLES" in msg
    assert _PROVEN_EXAMPLES_TEXT in msg


def test_proven_examples_section_omitted_when_none():
    state = _base_state()
    state["proven_examples"] = None

    msg = writer.build_writer_user_message(state)

    assert "## PROVEN EXAMPLES" not in msg


def test_proven_examples_section_omitted_when_absent():
    msg = writer.build_writer_user_message(_base_state())

    assert "## PROVEN EXAMPLES" not in msg


def test_proven_examples_section_ordering():
    """Appears after REFRAMING TARGETS, before REVISION/COMPILE sections."""
    state = _base_state()
    state["proven_examples"] = _PROVEN_EXAMPLES_TEXT
    state["writer_output"] = None
    state["iteration"] = 2
    state["revision_notes"] = ["Tighten bullet 1."]
    state["compile_errors"] = "Undefined control sequence \\emoji on line 42."

    msg = writer.build_writer_user_message(state)

    targets_pos = msg.index("## REFRAMING TARGETS")
    proven_pos = msg.index("## PROVEN EXAMPLES")
    revision_pos = msg.index("## REVISION NOTES")
    compile_pos = msg.index("## COMPILE ERRORS")

    assert targets_pos < proven_pos < revision_pos < compile_pos
