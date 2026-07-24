"""Tests for the bullet length validator — deterministic backstop for Writer output.

The validator runs post-Writer and pre-Renderer, catching bullets outside the
195-210 character band (min 195, max 210). Violations route back to Writer via
``length_violations``. NO live API calls — pure Python char counting.
"""
from src.agents.validators import (
    BULLET_HI,
    BULLET_LO,
    check_bullet_lengths,
    validate_bullet_lengths,
)
from src.pipeline.schemas import RoleBullets, WriterOutput


def test_band_constants_are_195_210():
    """The bullet band is min 195, max 210."""
    assert (BULLET_LO, BULLET_HI) == (195, 210)


def _valid_output() -> WriterOutput:
    """Writer output with all bullets in valid range (195-210 chars)."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "x" * 200,  # valid: 200 chars
                    "y" * 205,  # valid: 205 chars
                ],
            ),
        ],
    )


def _short_bullet_output() -> WriterOutput:
    """Writer output with one bullet too short."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "This is too short",  # 17 chars < 195
                ],
            ),
        ],
    )


def _long_bullet_output() -> WriterOutput:
    """Writer output with one bullet too long."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "x" * 230,  # 230 chars > 210
                ],
            ),
        ],
    )


def _mixed_violations_output() -> WriterOutput:
    """Writer output with multiple bullet violations across roles."""
    return WriterOutput(
        roles=[
            RoleBullets(
                index=0,
                bullets=[
                    "short",  # 5 chars < 195
                    "x" * 200,  # valid
                ],
            ),
            RoleBullets(
                index=1,
                bullets=[
                    "x" * 240,  # 240 chars > 210
                    "y" * 205,  # valid
                ],
            ),
        ],
    )


# --- validate_bullet_lengths function -------------------------------------------


def test_validate_bullet_lengths_accepts_valid_bullets():
    """All bullets in 195-210 range → no violations."""
    assert validate_bullet_lengths(_valid_output()) == []


def test_validate_bullet_lengths_rejects_short_bullet():
    """Bullet < 195 chars → violation with UNDERBUILT delta."""
    violations = validate_bullet_lengths(_short_bullet_output())

    assert len(violations) == 1
    assert "Role 0 bullet 0" in violations[0]
    assert "17 chars" in violations[0]
    assert "UNDERBUILT by 178" in violations[0]  # 195 - 17 = 178
    assert "Target: 195-210" in violations[0]
    assert "This is too short" in violations[0]


def test_validate_bullet_lengths_rejects_long_bullet():
    """Bullet > 210 chars → violation with BLOATED delta."""
    violations = validate_bullet_lengths(_long_bullet_output())

    assert len(violations) == 1
    assert "Role 0 bullet 0" in violations[0]
    assert "230 chars" in violations[0]
    assert "BLOATED by 20" in violations[0]  # 230 - 210 = 20
    assert "Target: 195-210" in violations[0]


def test_validate_bullet_lengths_reports_multiple_violations():
    """Multiple violations across roles → all reported (2 here)."""
    violations = validate_bullet_lengths(_mixed_violations_output())

    assert len(violations) == 2
    assert any("Role 0 bullet 0" in v and "UNDERBUILT" in v for v in violations)
    assert any("Role 1 bullet 0" in v and "BLOATED" in v for v in violations)


def test_validate_bullet_lengths_respects_custom_bounds():
    """Custom lo/hi bounds are respected."""
    output = WriterOutput(
        roles=[RoleBullets(index=0, bullets=["x" * 100])],
    )

    # 100 chars is invalid for default [195, 210]
    assert len(validate_bullet_lengths(output)) == 1
    # 100 chars is valid for custom [90, 110]
    assert validate_bullet_lengths(output, lo=90, hi=110) == []


def test_validate_bullet_lengths_empty_roles():
    """No roles → no violations."""
    output = WriterOutput(roles=[])
    assert validate_bullet_lengths(output) == []


def test_validate_bullet_lengths_empty_bullets():
    """Role with no bullets → no violations."""
    output = WriterOutput(roles=[RoleBullets(index=0, bullets=[])])
    assert validate_bullet_lengths(output) == []


# --- check_bullet_lengths node --------------------------------------------------


def test_check_bullet_lengths_writes_none_when_valid():
    """Valid output → length_violations=None, and length_retries is untouched.

    On a clean pass length_retries must be ABSENT from the return so LangGraph
    preserves the per-iteration counter (mirrors identity_check_node).
    """
    state = {"writer_output": _valid_output(), "length_retries": 2}
    out = check_bullet_lengths(state)

    assert set(out.keys()) == {"length_violations"}
    assert out["length_violations"] is None
    assert "length_retries" not in out


def test_check_bullet_lengths_writes_violations_when_invalid():
    """Invalid output → length_violations=list[str] AND length_retries bumped."""
    state = {"writer_output": _short_bullet_output()}
    out = check_bullet_lengths(state)

    assert set(out.keys()) == {"length_violations", "length_retries"}
    violations = out["length_violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "UNDERBUILT" in violations[0]
    # First violation: counter starts from the default 0 → 1.
    assert out["length_retries"] == 1


def test_check_bullet_lengths_increments_existing_retry_counter():
    """length_retries increments from whatever was already on the state."""
    state = {"writer_output": _short_bullet_output(), "length_retries": 2}
    out = check_bullet_lengths(state)

    assert out["length_retries"] == 3


def test_check_bullet_lengths_reports_multiple_violations():
    """Multiple violations → all returned in violations list."""
    state = {"writer_output": _mixed_violations_output()}
    out = check_bullet_lengths(state)

    assert len(out["length_violations"]) == 2


def test_check_bullet_lengths_does_not_mutate_input_state():
    """Node does not mutate the input state dict."""
    state = {"writer_output": _valid_output()}
    snapshot_keys = set(state.keys())
    check_bullet_lengths(state)

    assert set(state.keys()) == snapshot_keys
    assert "length_violations" not in state
