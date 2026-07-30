"""Tests for VaultSettings - the enable/disable switch for the vault."""
from __future__ import annotations

import os
import tempfile

import pytest

from src.vault.config import VaultSettings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure RESUME_VAULT_DIR never leaks in from the real environment."""
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)


def test_load_enabled_when_env_points_to_existing_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setenv("RESUME_VAULT_DIR", tmp_dir)

        settings = VaultSettings.load()

        assert settings.enabled is True
        assert str(settings.dir) == tmp_dir


def test_load_disabled_when_env_unset():
    settings = VaultSettings.load()

    assert settings.enabled is False
    assert settings.dir is None


def test_load_disabled_when_env_blank(monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", "   ")

    settings = VaultSettings.load()

    assert settings.enabled is False
    assert settings.dir is None


def test_load_creates_dir_when_missing_but_creatable(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = os.path.join(tmp_dir, "nested", "vault")
        monkeypatch.setenv("RESUME_VAULT_DIR", target)

        settings = VaultSettings.load()

        assert settings.enabled is True
        assert os.path.isdir(target)


def test_load_disabled_when_dir_path_is_a_file(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "not_a_dir")
        with open(file_path, "w") as f:
            f.write("i am a file")
        monkeypatch.setenv("RESUME_VAULT_DIR", file_path)

        settings = VaultSettings.load()

        assert settings.enabled is False


def test_vault_settings_is_frozen(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setenv("RESUME_VAULT_DIR", tmp_dir)
        settings = VaultSettings.load()

        with pytest.raises(Exception):
            settings.enabled = False
