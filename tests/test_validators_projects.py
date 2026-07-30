"""Tests for project bullet validation and locking in check_bullet_lengths."""
from src.agents.validators import validate_bullet_lengths, check_bullet_lengths
from src.pipeline.schemas import ProjectBullets, RoleBullets, WriterOutput


def _make_valid_bullet(n: int = 200) -> str:
    return "A" * n


def _make_output(role_bullets=None, project_bullets=None) -> WriterOutput:
    roles = role_bullets or []
    projects = project_bullets or []
    return WriterOutput(roles=roles, projects=projects)


class TestValidateBulletLengthsProjects:
    def test_valid_project_bullets_no_violations(self):
        pb = ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(200), _make_valid_bullet(205)])
        out = _make_output(project_bullets=[pb])
        violations = validate_bullet_lengths(out)
        assert violations == []

    def test_underbuilt_project_bullet_flagged(self):
        pb = ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(100)])
        out = _make_output(project_bullets=[pb])
        violations = validate_bullet_lengths(out)
        assert len(violations) == 1
        assert "Project 1" in violations[0]
        assert "UNDERBUILT" in violations[0]

    def test_bloated_project_bullet_flagged(self):
        pb = ProjectBullets(rank=2, heading="T", bullets=[_make_valid_bullet(220)])
        out = _make_output(project_bullets=[pb])
        violations = validate_bullet_lengths(out)
        assert len(violations) == 1
        assert "Project 2" in violations[0]
        assert "BLOATED" in violations[0]

    def test_role_and_project_violations_combined(self):
        roles = [RoleBullets(index=0, bullets=[_make_valid_bullet(100)])]
        projects = [ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(220)])]
        out = _make_output(role_bullets=roles, project_bullets=projects)
        violations = validate_bullet_lengths(out)
        assert len(violations) == 2

    def test_empty_projects_no_violations(self):
        out = _make_output()
        violations = validate_bullet_lengths(out)
        assert violations == []


class TestCheckBulletLengthsNode:
    def _state_without_project_bullets(self, writer_output: WriterOutput) -> dict:
        return {"writer_output": writer_output}

    def _state_with_project_bullets(self, writer_output: WriterOutput, locked: list) -> dict:
        return {"writer_output": writer_output, "project_bullets": locked}

    def test_sets_project_bullets_on_first_pass(self):
        pb = [ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(200), _make_valid_bullet(200), _make_valid_bullet(200)])]
        out = _make_output(project_bullets=pb)
        state = self._state_without_project_bullets(out)
        result = check_bullet_lengths(state)
        assert "project_bullets" in result
        assert result["project_bullets"] == pb

    def test_does_not_overwrite_locked_project_bullets(self):
        locked = [ProjectBullets(rank=1, heading="Locked", bullets=[_make_valid_bullet(200)])]
        new_pb = [ProjectBullets(rank=1, heading="New", bullets=[_make_valid_bullet(200)])]
        out = _make_output(project_bullets=new_pb)
        state = self._state_with_project_bullets(out, locked)
        result = check_bullet_lengths(state)
        assert "project_bullets" not in result  # locked, not re-set

    def test_no_project_bullets_in_output_does_not_set_state(self):
        out = _make_output()
        state = self._state_without_project_bullets(out)
        result = check_bullet_lengths(state)
        assert "project_bullets" not in result

    def test_violation_routes_back_to_writer(self):
        pb = [ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(100)])]
        out = _make_output(project_bullets=pb)
        state = self._state_without_project_bullets(out)
        result = check_bullet_lengths(state)
        assert result["length_violations"]
        assert len(result["length_violations"]) == 1

    def test_does_not_lock_project_bullets_when_violations_exist(self):
        """Violated project bullets must not be locked — writer needs a chance to fix them."""
        pb = [ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(100)])]
        out = _make_output(project_bullets=pb)
        state = self._state_without_project_bullets(out)
        result = check_bullet_lengths(state)
        assert "project_bullets" not in result
