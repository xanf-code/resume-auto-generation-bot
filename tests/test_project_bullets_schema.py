"""Tests for ProjectBullets, SelectedProject, and WriterOutput.projects schema additions."""
import json

import pytest
from pydantic import ValidationError

from src.pipeline.schemas import ProjectBullets, SelectedProject, WriterOutput, RoleBullets


class TestProjectBullets:
    def test_valid_k1(self):
        pb = ProjectBullets(rank=1, heading="Real-Time Job Aggregation Engine", bullets=["a", "b", "c"])
        assert pb.rank == 1
        assert pb.heading == "Real-Time Job Aggregation Engine"
        assert len(pb.bullets) == 3

    def test_valid_k2(self):
        pb = ProjectBullets(rank=2, heading="AI Financial Audit Platform", bullets=["x", "y"])
        assert pb.rank == 2
        assert len(pb.bullets) == 2

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ProjectBullets(rank=1, heading="T", bullets=[], extra_field="no")

    def test_round_trip_json(self):
        pb = ProjectBullets(rank=1, heading="Test Project", bullets=["bullet one", "bullet two"])
        serialized = pb.model_dump_json()
        restored = ProjectBullets.model_validate_json(serialized)
        assert restored == pb


class TestSelectedProject:
    def test_valid(self):
        sp = SelectedProject(
            rank=1,
            id="goonedin",
            context="Real-time job aggregation using FastAPI and websockets.",
            link="https://goonedin.vercel.app/",
            bullet_count=3,
        )
        assert sp.rank == 1
        assert sp.bullet_count == 3

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            SelectedProject(rank=1, id="x", context="c", link="l", bullet_count=3, bad="no")

    def test_round_trip_json(self):
        sp = SelectedProject(rank=2, id="spendai", context="Finance AI.", link="https://github.com/x", bullet_count=2)
        restored = SelectedProject.model_validate_json(sp.model_dump_json())
        assert restored == sp


class TestWriterOutputProjects:
    def test_projects_defaults_to_empty(self):
        out = WriterOutput(roles=[])
        assert out.projects == []

    def test_writer_output_with_projects(self):
        out = WriterOutput(
            roles=[RoleBullets(index=0, bullets=["Built a pipeline"])],
            projects=[
                ProjectBullets(rank=1, heading="K1 Title", bullets=["b1", "b2", "b3"]),
                ProjectBullets(rank=2, heading="K2 Title", bullets=["b4", "b5"]),
            ],
        )
        assert len(out.projects) == 2
        assert out.projects[0].rank == 1
        assert out.projects[1].rank == 2

    def test_writer_output_round_trip(self):
        out = WriterOutput(
            roles=[RoleBullets(index=0, bullets=["Built API endpoints"])],
            projects=[ProjectBullets(rank=1, heading="T", bullets=["x"])],
        )
        restored = WriterOutput.model_validate_json(out.model_dump_json())
        assert restored.projects[0].heading == "T"
