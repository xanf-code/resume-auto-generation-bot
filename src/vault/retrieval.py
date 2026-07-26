"""Retrieval of proven bullets from past winning runs (Loop A, read side).

Surfaces bullets from prior runs that earned an interview or offer for a
similar role, so the writer can reuse framing that already worked instead of
starting cold every time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from src.vault.config import VaultSettings
from src.vault.notes import Note, load_all_runs

_WIN_OUTCOMES = frozenset({"interview", "offer"})
_PENDING_STALE_AFTER = timedelta(days=30)
_FINAL_BULLETS_HEADING = "## Final bullets"
_PROVEN_EXAMPLES_HEADER = (
    "## PROVEN EXAMPLES (bullets that earned interviews for similar roles — "
    "match framing/emphasis, do not invent facts)"
)


def retrieve_examples(
    tags: Iterable[str], *, settings: VaultSettings, k: int = 3
) -> str | None:
    """Return a prompt-ready block of bullets from past runs that earned an
    interview for a similar role, or ``None`` when nothing qualifies.
    """
    tag_set = set(tags)
    ranked = []
    for note in load_all_runs(settings):
        if _resolve_outcome(note) not in _WIN_OUTCOMES:
            continue
        overlap = len(tag_set & set(note.frontmatter.get("jd_type") or []))
        if overlap == 0:
            continue
        ranked.append((overlap, note.frontmatter.get("internal_score", 0), note))

    if not ranked:
        return None

    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    blocks = [_extract_final_bullets(note.body) for _, _, note in ranked[:k]]
    return "\n\n".join([_PROVEN_EXAMPLES_HEADER, *blocks])


def _resolve_outcome(note: Note) -> str:
    outcome = note.frontmatter.get("outcome")
    if outcome == "pending" and _is_stale_pending(note):
        return "no_response"
    return outcome


def _is_stale_pending(note: Note) -> bool:
    created_raw = note.frontmatter.get("created")
    if not created_raw:
        return False
    created = datetime.fromisoformat(created_raw)
    return datetime.now(timezone.utc) - created > _PENDING_STALE_AFTER


def _extract_final_bullets(body: str) -> str:
    start = body.find(_FINAL_BULLETS_HEADING)
    if start == -1:
        return ""
    rest = body[start + len(_FINAL_BULLETS_HEADING) :]
    end = rest.find("\n## ")
    return (rest if end == -1 else rest[:end]).strip()
