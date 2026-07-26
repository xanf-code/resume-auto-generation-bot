"""Tests for vault note I/O - read/write round-tripping and run loading."""
from __future__ import annotations

import os

import pytest

from src.vault.config import VaultSettings
from src.vault.notes import load_all_runs, read_note, write_note


def test_write_then_read_roundtrips_frontmatter_and_body(tmp_path):
    path = tmp_path / "note.md"
    fm_data = {
        "title": "Run 42",
        "tags": ["ok", "fail"],
        "meta": {"score": 7, "items": [1, 2, 3]},
    }
    body = "# Heading\n\nSome body text with **markdown**.\nSecond line."

    write_note(path, fm_data, body)
    note = read_note(path)

    assert note.frontmatter == fm_data
    assert note.body == body
    assert note.path == path


def test_write_note_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "deep" / "note.md"

    write_note(path, {"a": 1}, "body")

    assert path.exists()
    note = read_note(path)
    assert note.frontmatter == {"a": 1}


def test_write_note_atomic_leaves_no_partial_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "note.md"

    def _boom(*args, **kwargs):
        raise OSError("simulated failure")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError):
        write_note(target, {"a": 1}, "body")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_load_all_runs_returns_notes_sorted_deterministically(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    settings = VaultSettings.load()

    runs_dir = tmp_path / "runs"
    write_note(runs_dir / "b-run.md", {"id": "b"}, "body b")
    write_note(runs_dir / "a-run.md", {"id": "a"}, "body a")
    write_note(runs_dir / "c-run.md", {"id": "c"}, "body c")

    notes = load_all_runs(settings)

    assert [n.frontmatter["id"] for n in notes] == ["a", "b", "c"]


def test_load_all_runs_empty_when_runs_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    settings = VaultSettings.load()

    assert load_all_runs(settings) == []


def test_load_all_runs_disabled_returns_empty_without_touching_filesystem(monkeypatch):
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)
    settings = VaultSettings.load()
    assert settings.enabled is False

    def _boom(*args, **kwargs):
        raise AssertionError("filesystem should not be touched when vault disabled")

    monkeypatch.setattr("pathlib.Path.is_dir", _boom)
    monkeypatch.setattr("pathlib.Path.glob", _boom)

    assert load_all_runs(settings) == []
