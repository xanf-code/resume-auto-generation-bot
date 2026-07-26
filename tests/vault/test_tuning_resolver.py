"""Tests for resolve_tuning - the Loop B apply-side tuning override merger."""
from __future__ import annotations

import json

import pytest

from src.pipeline.tuning import PipelineTuning
from src.vault.config import VaultSettings
from src.vault.tuning import resolve_tuning


@pytest.fixture
def settings(tmp_path, monkeypatch) -> VaultSettings:
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    return VaultSettings.load()


def _write_active_json(settings: VaultSettings, by_tag: dict) -> None:
    tuning_dir = settings.dir / "tuning"
    tuning_dir.mkdir(parents=True, exist_ok=True)
    (tuning_dir / "active.json").write_text(json.dumps({"by_tag": by_tag}))


def test_merge_applies_overrides_unlisted_fields_fall_back_to_defaults(settings):
    _write_active_json(settings, {"backend": {"threshold": 82, "max_iterations": 6}})

    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    defaults = PipelineTuning.defaults()
    assert tuning.threshold == 82
    assert tuning.max_iterations == 6
    assert tuning.plausibility_floor == defaults.plausibility_floor
    assert tuning.max_compile_retries == defaults.max_compile_retries
    assert tuning.max_identity_retries == defaults.max_identity_retries
    assert tuning.max_length_retries == defaults.max_length_retries
    assert diff["threshold"] == (defaults.threshold, 82)
    assert diff["max_iterations"] == (defaults.max_iterations, 6)


def test_most_specific_match_wins_among_multiple_by_tag_keys(settings):
    _write_active_json(
        settings,
        {
            "backend": {"threshold": 70},
            "backend+senior": {"threshold": 90},
            "frontend+senior": {"threshold": 50},
        },
    )

    tuning, diff = resolve_tuning(["backend", "senior"], None, settings=settings)

    assert tuning.threshold == 90
    assert diff["threshold"] == (PipelineTuning.defaults().threshold, 90)


def test_non_subset_keys_are_ignored(settings):
    _write_active_json(settings, {"frontend+staff": {"threshold": 12}})

    tuning, diff = resolve_tuning(["backend", "senior"], None, settings=settings)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_weights_renormalize_to_1_0_after_partial_override(settings):
    _write_active_json(
        settings, {"backend": {"rubric_weights": {"keyword_match": 0.9}}}
    )

    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    assert pytest.approx(sum(tuning.rubric_weights.values()), abs=1e-9) == 1.0
    assert "rubric_weights" in diff


def test_precedence_explicit_job_tuning_beats_vault_override(settings):
    _write_active_json(settings, {"backend": {"threshold": 99}})

    explicit = PipelineTuning.defaults()
    tuning, diff = resolve_tuning(["backend"], explicit, settings=settings)

    assert tuning == explicit
    assert diff == {}


def test_disabled_vault_returns_base_and_empty_diff(monkeypatch):
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)
    disabled = VaultSettings.load()
    assert disabled.enabled is False

    tuning, diff = resolve_tuning(["backend"], None, settings=disabled)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_no_match_returns_base_and_empty_diff(settings):
    _write_active_json(settings, {"frontend": {"threshold": 10}})

    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_missing_active_json_returns_base_and_empty_diff(settings):
    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_malformed_json_returns_base_and_empty_diff_no_raise(settings):
    tuning_dir = settings.dir / "tuning"
    tuning_dir.mkdir(parents=True, exist_ok=True)
    (tuning_dir / "active.json").write_text("{not valid json")

    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_malformed_by_tag_shape_returns_base_and_empty_diff_no_raise(settings):
    tuning_dir = settings.dir / "tuning"
    tuning_dir.mkdir(parents=True, exist_ok=True)
    (tuning_dir / "active.json").write_text(json.dumps({"by_tag": "not-a-dict"}))

    tuning, diff = resolve_tuning(["backend"], None, settings=settings)

    assert tuning == PipelineTuning.defaults()
    assert diff == {}


def test_returned_tuning_is_frozen(settings):
    _write_active_json(settings, {"backend": {"threshold": 82}})

    tuning, _ = resolve_tuning(["backend"], None, settings=settings)

    with pytest.raises(Exception):
        tuning.threshold = 100
