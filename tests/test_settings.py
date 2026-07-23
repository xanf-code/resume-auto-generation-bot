"""Tests for config.settings — constants and require_api_key."""
import importlib

import pytest


def test_module_imports_without_api_key(monkeypatch):
    """Importing settings must NEVER require the API key."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import config.settings as settings

    importlib.reload(settings)  # re-import under a key-less env
    assert settings is not None


def test_constant_values():
    import config.settings as settings

    assert settings.THRESHOLD == 78
    assert settings.MAX_ITERATIONS == 6
    assert settings.MAX_COMPILE_RETRIES == 4
    assert settings.PLAUSIBILITY_FLOOR == 20
    assert settings.MODEL_STRONG == "claude-opus-4-8"
    assert settings.MODEL_FAST == "claude-haiku-4-5"


def test_rubric_weights_exact():
    import config.settings as settings

    assert settings.RUBRIC_WEIGHTS == {
        "keyword_match":  0.30,
        "impact_quality": 0.20,
        "coherence":      0.20,
        "plausibility":   0.15,
        "formatting":     0.15,
    }


def test_rubric_weights_sum_to_one():
    import config.settings as settings

    assert abs(sum(settings.RUBRIC_WEIGHTS.values()) - 1.0) < 1e-9


def test_require_api_key_raises_when_unset(monkeypatch):
    import config.settings as settings

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        settings.require_api_key()


def test_require_api_key_raises_when_empty(monkeypatch):
    import config.settings as settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(RuntimeError):
        settings.require_api_key()


def test_require_api_key_returns_value_when_set(monkeypatch):
    import config.settings as settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-value")
    assert settings.require_api_key() == "sk-test-value"
