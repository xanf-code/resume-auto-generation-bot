"""Tests for SELECTED PROJECTS block in build_writer_user_message."""
import pytest

from src.agents.writer import build_writer_user_message
from src.pipeline.schemas import (
    IdentityLedger,
    JDVector,
    ProjectBullets,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    Role,
    SelectedProject,
    SkillWeight,
)


def _base_state() -> dict:
    return {
        "resume_struct": ResumeStruct(
            roles=[
                ResumeRole(
                    company="Acme",
                    title="SWE",
                    start="2022",
                    end="2024",
                    source_evidence=["Built APIs"],
                )
            ],
            education=["BS CS"],
            skills=["Python"],
        ),
        "jd_vector": JDVector(
            weighted_skills=[SkillWeight(name="Python", weight=0.9)],
            ats_keywords=["Python", "REST"],
            seniority="mid",
            must_mirror=["REST"],
        ),
        "gap_targets": [
            ReframingTarget(
                competency="REST APIs",
                weight=0.9,
                host_role_index=0,
                real_evidence=["Built APIs"],
                framing_guidance="Frame as REST API development",
                no_evidence=False,
            )
        ],
    }


def _selected_projects() -> list[SelectedProject]:
    return [
        SelectedProject(rank=1, id="goonedin", context="Real-time job aggregation via WebSockets.", link="https://goonedin.vercel.app/", bullet_count=3),
        SelectedProject(rank=2, id="spendai", context="AI spend tracking with PII detection.", link="https://github.com/spendai", bullet_count=2),
    ]


class TestWriterUserMessageProjects:
    def test_no_project_block_when_selected_projects_absent(self):
        state = _base_state()
        msg = build_writer_user_message(state)
        assert "SELECTED PROJECTS" not in msg

    def test_no_project_block_when_project_bullets_already_locked(self):
        state = _base_state()
        state["selected_projects"] = _selected_projects()
        state["project_bullets"] = [ProjectBullets(rank=1, heading="Locked", bullets=["b1", "b2", "b3"])]
        msg = build_writer_user_message(state)
        assert "SELECTED PROJECTS" not in msg

    def test_project_block_included_on_first_iteration(self):
        state = _base_state()
        state["selected_projects"] = _selected_projects()
        # project_bullets NOT in state → first iteration
        msg = build_writer_user_message(state)
        assert "SELECTED PROJECTS" in msg

    def test_k1_context_and_bullet_count_in_message(self):
        state = _base_state()
        state["selected_projects"] = _selected_projects()
        msg = build_writer_user_message(state)
        assert "Real-time job aggregation via WebSockets" in msg
        assert "3 bullets" in msg or "3" in msg

    def test_k2_context_and_bullet_count_in_message(self):
        state = _base_state()
        state["selected_projects"] = _selected_projects()
        msg = build_writer_user_message(state)
        assert "AI spend tracking with PII detection" in msg
        assert "2 bullets" in msg or "2" in msg

    def test_project_block_absent_when_selected_projects_is_empty_list(self):
        state = _base_state()
        state["selected_projects"] = []
        msg = build_writer_user_message(state)
        assert "SELECTED PROJECTS" not in msg
