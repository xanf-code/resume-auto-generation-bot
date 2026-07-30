"""Tests for project bullet validation and locking in check_bullet_lengths."""
from src.agents.validators import validate_bullet_lengths, check_bullet_lengths
from src.pipeline.schemas import InventedTool, ProjectBullets, RoleBullets, WriterOutput


def _make_valid_bullet(n: int = 200) -> str:
    return "A" * n


def _make_output(role_bullets=None, project_bullets=None, invented_stack=None) -> WriterOutput:
    roles = role_bullets or []
    projects = project_bullets or []
    kwargs = {}
    if invented_stack is not None:
        kwargs["invented_stack"] = invented_stack
    return WriterOutput(roles=roles, projects=projects, **kwargs)


def _make_ledger() -> list[InventedTool]:
    return [
        InventedTool(
            tool="Kafka",
            introduced_in="role 0 bullet 2",
            supporting_detail="partitioned by customer_id for ordered replay",
            reused_in=["role 1 bullet 1"],
        ),
    ]


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


class TestCheckBulletLengthsInventedStackLock:
    """The invention ledger gets the same first-pass lock as project_bullets."""

    def test_sets_invented_stack_on_clean_first_pass(self):
        ledger = _make_ledger()
        out = _make_output(invented_stack=ledger)
        result = check_bullet_lengths({"writer_output": out})
        assert result["invented_stack"] == ledger

    def test_does_not_overwrite_locked_invented_stack(self):
        locked = _make_ledger()
        new_ledger = [
            InventedTool(
                tool="Redis",
                introduced_in="role 1 bullet 0",
                supporting_detail="cache-aside pattern",
                reused_in=[],
            ),
        ]
        out = _make_output(invented_stack=new_ledger)
        state = {"writer_output": out, "invented_stack": locked}
        result = check_bullet_lengths(state)
        assert "invented_stack" not in result

    def test_empty_invented_stack_in_output_does_not_set_state(self):
        out = _make_output()
        result = check_bullet_lengths({"writer_output": out})
        assert "invented_stack" not in result

    def test_does_not_lock_invented_stack_when_violations_exist(self):
        """A ledger from a still-violating draft must not be frozen."""
        pb = [ProjectBullets(rank=1, heading="T", bullets=[_make_valid_bullet(100)])]
        out = _make_output(project_bullets=pb, invented_stack=_make_ledger())
        result = check_bullet_lengths({"writer_output": out})
        assert "invented_stack" not in result
