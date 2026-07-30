"""Database configuration — reads Supabase credentials from environment variables.

Importing this module never raises; ``load_db_settings`` raises ``RuntimeError``
only if the required env vars are absent (called lazily at app startup).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DbSettings:
    """Immutable Supabase connection settings."""

    url: str
    service_key: str
    bucket: str = "resumes"


def load_db_settings() -> DbSettings:
    """Build ``DbSettings`` from environment variables.

    Required: ``SUPABASE_URL``, ``SUPABASE_SERVICE_ROLE_KEY``
    Optional: ``SUPABASE_BUCKET`` (default ``"resumes"``)

    Raises:
        RuntimeError: if any required variable is absent or blank.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not service_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required Supabase env vars: {', '.join(missing)}"
        )

    bucket = os.environ.get("SUPABASE_BUCKET", "resumes").strip() or "resumes"
    return DbSettings(url=url, service_key=service_key, bucket=bucket)
