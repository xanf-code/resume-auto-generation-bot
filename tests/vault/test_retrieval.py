"""Tests for vault retrieval - surfacing proven bullets from past winning runs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.vault.config import VaultSettings
from src.vault.notes import write_note
from src.vault.retrieval import retrieve_examples


def _note(
    runs_dir,
    name,
    *,
    outcome,
    jd_type,
    internal_score=70,
    created=None,
    bullets="- Did a thing.",
):
    created = created or datetime.now(timezone.utc)
    fm = {
        "job_id": name,
        "jd_type": jd_type,
        "outcome": outcome,
        "internal_score": internal_score,
        "created": created.isoformat(),
    }
    body = f"## Final bullets\n{bullets}\n\n## Score breakdown\nAggregate: {internal_score}\n"
    write_note(runs_dir / f"{name}.md", fm, body)


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    return VaultSettings.load()


def test_win_only_filter_excludes_non_wins(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(runs_dir, "rejected", outcome="rejected", jd_type=["backend"])
    _note(runs_dir, "no_response", outcome="no_response", jd_type=["backend"])
    _note(runs_dir, "pending", outcome="pending", jd_type=["backend"])
    _note(
        runs_dir,
        "interview",
        outcome="interview",
        jd_type=["backend"],
        bullets="- Won this one.",
    )
    _note(
        runs_dir,
        "offer",
        outcome="offer",
        jd_type=["backend"],
        bullets="- Won this one too.",
    )

    result = retrieve_examples(["backend"], settings=settings)

    assert result is not None
    assert "Won this one." in result
    assert "Won this one too." in result
    assert "rejected" not in result.lower()
    assert "no_response" not in result.lower()


def test_requires_tag_overlap(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "frontend-win",
        outcome="interview",
        jd_type=["frontend"],
        bullets="- Frontend bullet.",
    )

    assert retrieve_examples(["backend"], settings=settings) is None


def test_stale_pending_excluded(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"
    old = datetime.now(timezone.utc) - timedelta(days=45)

    _note(
        runs_dir,
        "stale-pending",
        outcome="pending",
        jd_type=["backend"],
        created=old,
        bullets="- Should not appear.",
    )

    assert retrieve_examples(["backend"], settings=settings) is None


def test_ranking_by_overlap_then_score_respects_k(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "low-overlap-high-score",
        outcome="interview",
        jd_type=["backend"],
        internal_score=95,
        bullets="- Low overlap.",
    )
    _note(
        runs_dir,
        "high-overlap-low-score",
        outcome="interview",
        jd_type=["backend", "platform"],
        internal_score=50,
        bullets="- High overlap.",
    )
    _note(
        runs_dir,
        "high-overlap-high-score",
        outcome="offer",
        jd_type=["backend", "platform"],
        internal_score=90,
        bullets="- Best match.",
    )

    result = retrieve_examples(["backend", "platform"], settings=settings, k=2)

    assert result is not None
    assert "Best match." in result
    assert "High overlap." in result
    assert "Low overlap." not in result


def test_cold_start_returns_none(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    assert retrieve_examples(["backend"], settings=settings) is None


def test_disabled_vault_returns_none(monkeypatch):
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)
    settings = VaultSettings.load()
    assert settings.enabled is False

    assert retrieve_examples(["backend"], settings=settings) is None


def test_output_has_labelled_header(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"
    _note(
        runs_dir,
        "win",
        outcome="interview",
        jd_type=["backend"],
        bullets="- A bullet.",
    )

    result = retrieve_examples(["backend"], settings=settings)

    assert result.startswith(
        "## PROVEN EXAMPLES (bullets that earned interviews for similar roles"
    )
    assert "A bullet." in result
