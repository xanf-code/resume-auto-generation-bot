"""Tests for vault retrieval - surfacing proven bullets from past winning runs.

Retrieval hard-filters on ``role`` equality (no partial credit) and only ranks
on ``domains`` (Jaccard) within the same role - the fix for the production
bad-match bug (a Backend win leaking into a Product Owner run via shared
tech-flavor tags).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.vault.config import VaultSettings
from src.vault.notes import write_note
from src.vault.retrieval import _jaccard, retrieve_examples


def _note(
    runs_dir,
    name,
    *,
    outcome,
    role=None,
    domains=None,
    jd_type=None,
    internal_score=70,
    created=None,
    bullets="- Did a thing.",
    include_role_field=True,
):
    created = created or datetime.now(timezone.utc)
    domains = domains if domains is not None else []
    fm = {
        "job_id": name,
        "jd_type": jd_type if jd_type is not None else ([role, *domains] if role else list(domains)),
        "outcome": outcome,
        "internal_score": internal_score,
        "created": created.isoformat(),
        "domains": domains,
    }
    if include_role_field:
        fm["role"] = role
    body = f"## Final bullets\n{bullets}\n\n## Score breakdown\nAggregate: {internal_score}\n"
    write_note(runs_dir / f"{name}.md", fm, body)


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_VAULT_DIR", str(tmp_path))
    return VaultSettings.load()


def test_win_only_filter_excludes_non_wins(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(runs_dir, "rejected", outcome="rejected", role="backend")
    _note(runs_dir, "no_response", outcome="no_response", role="backend")
    _note(runs_dir, "pending", outcome="pending", role="backend")
    _note(
        runs_dir,
        "interview",
        outcome="interview",
        role="backend",
        bullets="- Won this one.",
    )
    _note(
        runs_dir,
        "offer",
        outcome="offer",
        role="backend",
        bullets="- Won this one too.",
    )

    result = retrieve_examples("backend", [], settings=settings)

    assert result is not None
    assert "Won this one." in result
    assert "Won this one too." in result
    assert "rejected" not in result.lower()
    assert "no_response" not in result.lower()


def test_role_mismatch_excluded_even_with_full_domain_overlap(tmp_path, monkeypatch):
    """The production bug's regression test.

    A Backend win with full domain overlap (`infra`, `platform`) must never be
    retrieved for a Product query, even though the old flat-tag overlap logic
    would have matched it.
    """
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "backend-win",
        outcome="interview",
        role="backend",
        domains=["infra-domain", "saas"],
        bullets="- Shipped a backend bullet.",
    )

    result = retrieve_examples("product", ["infra-domain", "saas"], settings=settings)

    assert result is None


def test_role_none_returns_none_regardless_of_notes(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "backend-win",
        outcome="interview",
        role="backend",
        domains=["ai"],
        bullets="- Shipped a backend bullet.",
    )

    assert retrieve_examples(None, ["ai"], settings=settings) is None


def test_stale_pending_excluded(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"
    old = datetime.now(timezone.utc) - timedelta(days=45)

    _note(
        runs_dir,
        "stale-pending",
        outcome="pending",
        role="backend",
        created=old,
        bullets="- Should not appear.",
    )

    assert retrieve_examples("backend", [], settings=settings) is None


def test_domain_ranking_within_role_bucket_respects_k(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "no-overlap",
        outcome="interview",
        role="backend",
        domains=[],
        internal_score=95,
        bullets="- No overlap.",
    )
    _note(
        runs_dir,
        "partial-overlap",
        outcome="interview",
        role="backend",
        domains=["ai"],
        internal_score=50,
        bullets="- Partial overlap.",
    )
    _note(
        runs_dir,
        "full-overlap",
        outcome="offer",
        role="backend",
        domains=["ai", "fintech"],
        internal_score=90,
        bullets="- Best match.",
    )

    result = retrieve_examples("backend", ["ai", "fintech"], settings=settings, k=2)

    assert result is not None
    assert "Best match." in result
    assert "Partial overlap." in result
    assert "No overlap." not in result


def test_domain_ranking_ties_broken_by_internal_score(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "equal-jaccard-low-score",
        outcome="interview",
        role="backend",
        domains=["ai"],
        internal_score=50,
        bullets="- Low score.",
    )
    _note(
        runs_dir,
        "equal-jaccard-high-score",
        outcome="interview",
        role="backend",
        domains=["ai"],
        internal_score=95,
        bullets="- High score.",
    )

    result = retrieve_examples("backend", ["ai"], settings=settings, k=1)

    assert result is not None
    assert "High score." in result
    assert "Low score." not in result


def test_legacy_note_without_role_field_is_excluded(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"

    _note(
        runs_dir,
        "legacy-win",
        outcome="interview",
        jd_type=["backend"],
        include_role_field=False,
        bullets="- Legacy bullet.",
    )

    assert retrieve_examples("backend", [], settings=settings) is None


def test_cold_start_returns_none(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    assert retrieve_examples("backend", [], settings=settings) is None


def test_disabled_vault_returns_none(monkeypatch):
    monkeypatch.delenv("RESUME_VAULT_DIR", raising=False)
    settings = VaultSettings.load()
    assert settings.enabled is False

    assert retrieve_examples("backend", [], settings=settings) is None


def test_output_has_labelled_header(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    runs_dir = tmp_path / "runs"
    _note(
        runs_dir,
        "win",
        outcome="interview",
        role="backend",
        bullets="- A bullet.",
    )

    result = retrieve_examples("backend", [], settings=settings)

    assert result.startswith(
        "## PROVEN EXAMPLES (bullets that earned interviews for similar roles"
    )
    assert "A bullet." in result


def test_jaccard_disjoint_is_zero():
    assert _jaccard({"ai"}, {"fintech"}) == 0.0


def test_jaccard_identical_non_empty_is_one():
    assert _jaccard({"ai", "fintech"}, {"ai", "fintech"}) == 1.0


def test_jaccard_both_empty_is_zero():
    assert _jaccard(set(), set()) == 0.0


def test_jaccard_partial_overlap_is_correct_ratio():
    assert _jaccard({"ai", "fintech"}, {"ai"}) == 0.5
