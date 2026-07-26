"""Thin, pure helpers for reading and writing vault Markdown notes.

Notes are plain Markdown files with a YAML frontmatter header, handled via
``python-frontmatter``. Writes are atomic (write to a sibling temp file, then
``os.replace``) so a crash mid-write never leaves a half-written note behind.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from src.vault.config import VaultSettings


@dataclass(frozen=True)
class Note:
    """A single vault note: its parsed frontmatter, body, and source path."""

    frontmatter: dict
    body: str
    path: Path


def read_note(path: Path) -> Note:
    """Read a Markdown note and parse its frontmatter and body."""
    post = frontmatter.load(str(path))
    return Note(frontmatter=dict(post.metadata), body=post.content, path=Path(path))


def write_note(path: Path, frontmatter_data: dict, body: str) -> None:
    """Write a Markdown note atomically, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    post = frontmatter.Post(body)
    post.metadata = dict(frontmatter_data)
    content = frontmatter.dumps(post)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_all_runs(settings: VaultSettings) -> list[Note]:
    """Load all run notes from ``<vault>/runs/*.md``, sorted by filename.

    Returns ``[]`` without touching the filesystem when the vault is disabled.
    """
    if not settings.enabled or settings.dir is None:
        return []

    runs_dir = settings.dir / "runs"
    if not runs_dir.is_dir():
        return []

    return [read_note(p) for p in sorted(runs_dir.glob("*.md"))]
