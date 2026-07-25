"""Tests for src.pipeline.tuning - the per-run tuning config.

``PipelineTuning`` captures the knobs that were previously fixed module
constants in ``config.settings``. ``defaults()`` MUST mirror those constants
exactly (single source of truth) so an absent config is byte-identical to the
historical behaviour.
"""
import dataclasses

import pytest

from config import settings
from src.pipeline.tuning import RUBRIC_KEYS, PipelineTuning, get_tuning


def test_defaults_mirror_settings_constants():
    t = PipelineTuning.defaults()
    assert t.threshold == settings.THRESHOLD
    assert t.plausibility_floor == settings.PLAUSIBILITY_FLOOR
    assert t.max_iterations == settings.MAX_ITERATIONS
    assert t.max_compile_retries == settings.MAX_COMPILE_RETRIES
    assert t.max_identity_retries == settings.MAX_IDENTITY_RETRIES
    assert t.max_length_retries == settings.MAX_LENGTH_RETRIES
    assert dict(t.rubric_weights) == settings.RUBRIC_WEIGHTS


def test_rubric_keys_cover_the_five_dimensions():
    assert set(RUBRIC_KEYS) == set(settings.RUBRIC_WEIGHTS)


def test_is_frozen():
    t = PipelineTuning.defaults()
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.threshold = 99  # type: ignore[misc]


def test_get_tuning_falls_back_to_defaults_when_absent():
    assert get_tuning({}) == PipelineTuning.defaults()
    assert get_tuning({"tuning": None}) == PipelineTuning.defaults()


def test_get_tuning_returns_supplied_config():
    custom = dataclasses.replace(PipelineTuning.defaults(), threshold=90)
    assert get_tuning({"tuning": custom}) is custom
    assert get_tuning({"tuning": custom}).threshold == 90
