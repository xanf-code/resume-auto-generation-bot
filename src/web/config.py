"""Web layer settings - read from the environment with sane defaults.

Importing this module never requires secrets; the OpenRouter key is still
resolved lazily by ``config.settings.require_api_key`` when a job actually runs.
"""
import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class WebSettings:
    """Immutable web-layer configuration."""

    max_concurrent_jobs: int = 3
    out_root: str = "out"
    event_buffer_max: int = 500
    host: str = "127.0.0.1"
    port: int = 8000


def _optional_db_settings():
    """Return a ``DbSettings`` when Supabase env vars are present, else ``None``.

    Importing this function never raises — secrets are resolved lazily.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None
    try:
        from src.db.config import DbSettings
        return DbSettings(
            url=url,
            service_key=key,
            bucket=os.environ.get("SUPABASE_BUCKET", "resumes"),
        )
    except Exception:
        return None


def load_settings() -> WebSettings:
    """Build ``WebSettings`` from environment variables (all optional)."""
    return WebSettings(
        max_concurrent_jobs=_env_int("RESUMEBOT_MAX_CONCURRENT_JOBS", 3),
        out_root=os.environ.get("RESUMEBOT_OUT_ROOT", "out"),
        event_buffer_max=_env_int("RESUMEBOT_EVENT_BUFFER_MAX", 500),
        host=os.environ.get("RESUMEBOT_HOST", "127.0.0.1"),
        port=_env_int("RESUMEBOT_PORT", 8000),
    )
