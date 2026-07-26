"""Vault configuration - reads the vault directory from the environment.

The vault is opt-in: importing this module never touches the filesystem, and
``VaultSettings.load()`` only enables the vault when ``RESUME_VAULT_DIR`` is
explicitly set to a directory that exists or can be created. Any other run
(env unset, blank, or pointing at a path that can't become a directory) stays
disabled so the pipeline is unaffected.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VaultSettings:
    """Immutable vault configuration."""

    dir: Path | None
    enabled: bool

    @classmethod
    def load(cls) -> "VaultSettings":
        """Build ``VaultSettings`` from the ``RESUME_VAULT_DIR`` env var."""
        raw = os.environ.get("RESUME_VAULT_DIR", "").strip()
        if not raw:
            return cls(dir=None, enabled=False)

        path = Path(raw).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            return cls(dir=path, enabled=False)

        return cls(dir=path, enabled=path.is_dir())
