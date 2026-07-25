"""Phase: Dynamic bullet-shape selection — TDD tests (write first, run second).

Tests for:
- BULLET_SHAPES catalog and SHAPE_NAMES tuple in src.prompts.writer
- build_shape_directive in src.agents.writer
- PipelineState.bullet_shapes channel
- WRITER_SYSTEM no longer contains the hardcoded SHAPE ROTATION block
"""
import pytest

from src.prompts.writer import BULLET_SHAPES, SHAPE_NAMES
from src.agents.writer import build_shape_directive


# ---------------------------------------------------------------------------
# Catalog sanity
# ---------------------------------------------------------------------------

def test_shape_names_contains_all_four():
    assert set(SHAPE_NAMES) == {"PAR", "RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"}
    assert len(SHAPE_NAMES) == 4


def test_bullet_shapes_catalog_has_all_four():
    assert set(BULLET_SHAPES.keys()) == {"PAR", "RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"}


def test_bullet_shapes_catalog_has_description_and_example():
    for name, info in BULLET_SHAPES.items():
        assert "description" in info, f"{name} missing description"
        assert "example" in info, f"{name} missing example"
        assert info["description"], f"{name} description is empty"
        assert info["example"], f"{name} example is empty"


def test_shape_names_order_matches_catalog_order():
    """SHAPE_NAMES must be in the same insertion order as BULLET_SHAPES."""
    assert list(SHAPE_NAMES) == list(BULLET_SHAPES.keys())


# ---------------------------------------------------------------------------
# build_shape_directive — full rotation (None / [] / all four)
# ---------------------------------------------------------------------------

def test_build_shape_directive_none_produces_full_rotation():
    directive = build_shape_directive(None)
    for name in SHAPE_NAMES:
        assert name in directive, f"Missing shape {name!r} in full rotation directive"
    assert "rotate" in directive.lower() or "SHAPE ROTATION" in directive


def test_build_shape_directive_empty_list_produces_full_rotation():
    directive = build_shape_directive([])
    for name in SHAPE_NAMES:
        assert name in directive
    assert "rotate" in directive.lower() or "SHAPE ROTATION" in directive


def test_build_shape_directive_all_four_same_as_none():
    all_four = list(SHAPE_NAMES)
    assert build_shape_directive(all_four) == build_shape_directive(None)


def test_build_shape_directive_all_four_same_as_empty():
    assert build_shape_directive(list(SHAPE_NAMES)) == build_shape_directive([])


def test_build_shape_directive_catalog_roundtrips_all_examples():
    """Every shape's example must appear (at least the start of it) in the full directive."""
    directive = build_shape_directive(None)
    for name, info in BULLET_SHAPES.items():
        snippet = info["example"][:25]
        assert snippet in directive, f"Example start for {name!r} missing from full rotation directive"


# ---------------------------------------------------------------------------
# build_shape_directive — single shape
# ---------------------------------------------------------------------------

def test_build_shape_directive_single_uses_only():
    directive = build_shape_directive(["PAR"])
    assert "USE ONLY PAR" in directive


def test_build_shape_directive_single_no_rotate_among_language():
    directive = build_shape_directive(["PAR"])
    assert "rotate only among" not in directive.lower()


def test_build_shape_directive_single_includes_definition():
    directive = build_shape_directive(["PAR"])
    info = BULLET_SHAPES["PAR"]
    assert info["description"] in directive


def test_build_shape_directive_single_excludes_other_definitions():
    directive = build_shape_directive(["PAR"])
    for name in ["RESULT-FIRST", "ACTION+STACK", "CONTEXT-PAR"]:
        info = BULLET_SHAPES[name]
        assert info["description"] not in directive, (
            f"Found {name} description in single-shape directive"
        )


def test_build_shape_directive_each_single_shape():
    """Each of the four shapes can be used as the sole shape."""
    for name in SHAPE_NAMES:
        directive = build_shape_directive([name])
        assert f"USE ONLY {name}" in directive
        assert BULLET_SHAPES[name]["description"] in directive


# ---------------------------------------------------------------------------
# build_shape_directive — subset (2 or 3 shapes)
# ---------------------------------------------------------------------------

def test_build_shape_directive_subset_rotates_among():
    directive = build_shape_directive(["PAR", "RESULT-FIRST"])
    assert "Rotate ONLY among" in directive


def test_build_shape_directive_subset_lists_selected_names():
    directive = build_shape_directive(["PAR", "RESULT-FIRST"])
    assert "PAR" in directive
    assert "RESULT-FIRST" in directive


def test_build_shape_directive_subset_includes_selected_definitions():
    directive = build_shape_directive(["PAR", "RESULT-FIRST"])
    for name in ["PAR", "RESULT-FIRST"]:
        info = BULLET_SHAPES[name]
        assert info["description"] in directive, f"Missing {name} definition"


def test_build_shape_directive_subset_excludes_unselected_definitions():
    directive = build_shape_directive(["PAR", "RESULT-FIRST"])
    for name in ["ACTION+STACK", "CONTEXT-PAR"]:
        info = BULLET_SHAPES[name]
        assert info["description"] not in directive, (
            f"Found unselected {name} definition in subset directive"
        )


def test_build_shape_directive_three_shape_subset():
    subset = ["PAR", "ACTION+STACK", "CONTEXT-PAR"]
    directive = build_shape_directive(subset)
    assert "Rotate ONLY among" in directive
    for name in subset:
        assert name in directive
        assert BULLET_SHAPES[name]["description"] in directive
    assert BULLET_SHAPES["RESULT-FIRST"]["description"] not in directive


# ---------------------------------------------------------------------------
# PipelineState — bullet_shapes channel
# ---------------------------------------------------------------------------

def test_pipeline_state_accepts_bullet_shapes_list():
    from src.pipeline.state import PipelineState
    state: PipelineState = {"bullet_shapes": ["PAR"]}
    assert state.get("bullet_shapes") == ["PAR"]


def test_pipeline_state_accepts_bullet_shapes_none():
    from src.pipeline.state import PipelineState
    state: PipelineState = {"bullet_shapes": None}
    assert state.get("bullet_shapes") is None


def test_pipeline_state_bullet_shapes_absent_returns_none():
    from src.pipeline.state import PipelineState
    state: PipelineState = {}
    assert state.get("bullet_shapes") is None


def test_pipeline_state_bullet_shapes_in_annotations():
    """bullet_shapes must be declared in PipelineState so LangGraph tracks it."""
    from src.pipeline.state import PipelineState
    assert "bullet_shapes" in PipelineState.__annotations__


# ---------------------------------------------------------------------------
# WRITER_SYSTEM — hardcoded block removed, per-run pointer added
# ---------------------------------------------------------------------------

def test_writer_system_has_no_hardcoded_shape_rotation_block():
    from src.prompts.writer import WRITER_SYSTEM
    assert "SHAPE ROTATION (mandatory - not a menu)" not in WRITER_SYSTEM


def test_writer_system_references_per_run_shape_directive():
    from src.prompts.writer import WRITER_SYSTEM
    assert "BULLET SHAPE DIRECTIVE" in WRITER_SYSTEM
