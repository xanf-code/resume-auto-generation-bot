"""Tests for bullet length validator — deterministic backstop for Writer output.

The validator runs post-Writer and pre-Renderer, catching bullets outside the
158-180 character range. Violations route back to Writer via length_violations.
NO live API calls — pure Python char counting.
"""
from src.agents.validators import check_bullet_lengths, validate_bullet_lengths
from src.pipeline.schemas import RoleBullets, WriterOutput


def _valid_output() -> WriterOutput:
    """Writer output with all bullets in valid range (158-180 chars)."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "x" * 170,  # valid: 170 chars
                    "y" * 165,  # valid: 165 chars
                ],
            ),
        ],
        skills=["Python", "SQL"],
        summary="Senior engineer with 5 years experience.",
    )


def _short_bullet_output() -> WriterOutput:
    """Writer output with one bullet too short."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "This is too short",  # 18 chars < 158
                ],
            ),
        ],
        skills=["Python"],
        summary="Summary text.",
    )


def _long_bullet_output() -> WriterOutput:
    """Writer output with one bullet too long."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "x" * 200,  # 200 chars > 180
                ],
            ),
        ],
        skills=["Python"],
        summary="Summary text.",
    )


def _mixed_violations_output() -> WriterOutput:
    """Writer output with multiple violations across roles."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "short",  # 5 chars < 158
                    "x" * 170,  # valid
                ],
            ),
            RoleBullets(
                index=1,
                bullets=[
                    "x" * 190,  # 190 chars > 180
                    "y" * 165,  # valid
                ],
            ),
        ],
        skills=["Python"],
        summary="Summary text.",
    )


# --- validate_bullet_lengths function -------------------------------------------


def test_validate_bullet_lengths_accepts_valid_bullets():
    """All bullets in 158-180 range → no violations."""
    violations = validate_bullet_lengths(_valid_output())
    assert violations == []


def test_validate_bullet_lengths_rejects_short_bullet():
    """Bullet < 158 chars → violation with SHORT delta."""
    violations = validate_bullet_lengths(_short_bullet_output())

    assert len(violations) == 1
    assert "Role 0 bullet 0" in violations[0]
    assert "17 chars" in violations[0]
    assert "SHORT by 141" in violations[0]  # 158 - 17 = 141
    assert "Target: 158-180" in violations[0]
    assert "This is too short" in violations[0]


def test_validate_bullet_lengths_rejects_long_bullet():
    """Bullet > 180 chars → violation with LONG delta."""
    violations = validate_bullet_lengths(_long_bullet_output())

    assert len(violations) == 1
    assert "Role 0 bullet 0" in violations[0]
    assert "200 chars" in violations[0]
    assert "LONG by 20" in violations[0]  # 200 - 180 = 20
    assert "Target: 158-180" in violations[0]


def test_validate_bullet_lengths_reports_multiple_violations():
    """Multiple violations across roles → all reported."""
    violations = validate_bullet_lengths(_mixed_violations_output())

    assert len(violations) == 2
    # Role 0 bullet 0 is short
    assert any("Role 0 bullet 0" in v and "SHORT" in v for v in violations)
    # Role 1 bullet 0 is long
    assert any("Role 1 bullet 0" in v and "LONG" in v for v in violations)


def test_validate_bullet_lengths_respects_custom_bounds():
    """Custom lo/hi bounds are respected."""
    output = WriterOutput(
        roles=[RoleBullets(index=0, bullets=["x" * 100])],
        skills=["Python"],
        summary="Summary.",
    )

    # 100 chars is invalid for default [158, 180]
    violations_default = validate_bullet_lengths(output)
    assert len(violations_default) == 1

    # 100 chars is valid for custom [90, 110]
    violations_custom = validate_bullet_lengths(output, lo=90, hi=110)
    assert violations_custom == []


def test_validate_bullet_lengths_empty_roles():
    """No roles → no violations."""
    output = WriterOutput(roles=[], skills=["Python"], summary="Summary.")
    violations = validate_bullet_lengths(output)
    assert violations == []


def test_validate_bullet_lengths_empty_bullets():
    """Role with no bullets → no violations."""
    output = WriterOutput(
        roles=[RoleBullets(index=0, bullets=[])],
        skills=["Python"],
        summary="Summary.",
    )
    violations = validate_bullet_lengths(output)
    assert violations == []


# --- check_bullet_lengths node --------------------------------------------------


def test_check_bullet_lengths_writes_none_when_valid():
    """Valid output → length_violations=None."""
    state = {"writer_output": _valid_output()}
    out = check_bullet_lengths(state)

    assert set(out.keys()) == {"length_violations"}
    assert out["length_violations"] is None


def test_check_bullet_lengths_writes_violations_when_invalid():
    """Invalid output → length_violations=list[str]."""
    state = {"writer_output": _short_bullet_output()}
    out = check_bullet_lengths(state)

    assert set(out.keys()) == {"length_violations"}
    violations = out["length_violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "SHORT" in violations[0]


def test_check_bullet_lengths_does_not_mutate_input_state():
    """Node does not mutate the input state dict."""
    state = {"writer_output": _valid_output()}
    snapshot_keys = set(state.keys())
    check_bullet_lengths(state)

    assert set(state.keys()) == snapshot_keys
    assert "length_violations" not in state


def test_check_bullet_lengths_reports_multiple_violations():
    """Multiple violations → all returned in violations list."""
    state = {"writer_output": _mixed_violations_output()}
    out = check_bullet_lengths(state)

    violations = out["length_violations"]
    assert len(violations) == 2
