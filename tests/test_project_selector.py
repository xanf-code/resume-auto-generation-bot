"""Tests for the project_selector node (mocked LLM calls)."""
from unittest.mock import patch

import pytest

from config.projects import PROJECTS
from src.agents.project_selector import (
    _assign_bullet_counts,
    _build_selector_prompt,
    project_select,
)
from src.pipeline.schemas import JDVector, SelectedProject, SkillWeight


def _jd() -> JDVector:
    return JDVector(
        weighted_skills=[
            SkillWeight(name="WebSockets", weight=0.9),
            SkillWeight(name="Python", weight=0.8),
            SkillWeight(name="FastAPI", weight=0.75),
        ],
        ats_keywords=["real-time", "WebSockets", "scraping", "JSON", "Python"],
        seniority="mid",
        must_mirror=["real-time", "WebSockets"],
    )


def _state(jd: JDVector | None = None) -> dict:
    return {"jd_vector": jd or _jd()}


class TestAssignBulletCounts:
    def test_rank1_gets_3(self):
        sp = SelectedProject(rank=1, id="x", context="c", link="l", bullet_count=0)
        result = _assign_bullet_counts([sp])
        assert result[0].bullet_count == 3

    def test_rank2_gets_2(self):
        sp = SelectedProject(rank=2, id="x", context="c", link="l", bullet_count=0)
        result = _assign_bullet_counts([sp])
        assert result[0].bullet_count == 2

    def test_counts_are_immutable_new_objects(self):
        sp = SelectedProject(rank=1, id="x", context="c", link="l", bullet_count=0)
        result = _assign_bullet_counts([sp])
        assert result[0] is not sp  # new object returned
        assert sp.bullet_count == 0  # original unchanged


class TestBuildSelectorPrompt:
    def test_contains_jd_keywords(self):
        prompt = _build_selector_prompt(_jd(), PROJECTS)
        assert "WebSockets" in prompt
        assert "real-time" in prompt

    def test_contains_all_project_contexts(self):
        prompt = _build_selector_prompt(_jd(), PROJECTS)
        for p in PROJECTS:
            assert p["context"][:40] in prompt

    def test_contains_project_ids(self):
        prompt = _build_selector_prompt(_jd(), PROJECTS)
        for p in PROJECTS:
            assert p["id"] in prompt


class TestProjectSelectNode:
    def _mock_selected(self) -> list[SelectedProject]:
        return [
            SelectedProject(rank=1, id="goonedin", context=PROJECTS[0]["context"], link=PROJECTS[0]["link"], bullet_count=3),
            SelectedProject(rank=2, id="neu-advisor", context=PROJECTS[2]["context"], link=PROJECTS[2]["link"], bullet_count=2),
        ]

    def test_returns_exactly_two_projects(self):
        with patch("src.agents.project_selector._llm_select", return_value=self._mock_selected()):
            result = project_select(_state())
        assert "selected_projects" in result
        assert len(result["selected_projects"]) == 2

    def test_k1_has_bullet_count_3(self):
        with patch("src.agents.project_selector._llm_select", return_value=self._mock_selected()):
            result = project_select(_state())
        k1 = next(sp for sp in result["selected_projects"] if sp.rank == 1)
        assert k1.bullet_count == 3

    def test_k2_has_bullet_count_2(self):
        with patch("src.agents.project_selector._llm_select", return_value=self._mock_selected()):
            result = project_select(_state())
        k2 = next(sp for sp in result["selected_projects"] if sp.rank == 2)
        assert k2.bullet_count == 2

    def test_selected_projects_contain_context_and_link(self):
        with patch("src.agents.project_selector._llm_select", return_value=self._mock_selected()):
            result = project_select(_state())
        for sp in result["selected_projects"]:
            assert sp.context
            assert sp.link
