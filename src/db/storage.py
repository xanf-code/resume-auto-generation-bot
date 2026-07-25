"""Supabase Storage helpers for resume PDF objects.

All functions are synchronous and safe to call from a ThreadPoolExecutor worker.
The bucket layout is flat: ``{job_id}/resume.pdf``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PDF_OBJECT_KEY = "{job_id}/resume.pdf"


def pdf_key(job_id: str) -> str:
    """Return the canonical Storage object key for a job's PDF."""
    return f"{job_id}/resume.pdf"


def upload_pdf(
    job_id: str,
    local_path: str,
    client: Any,
    bucket: str,
) -> str:
    """Read a PDF file and upload it to Supabase Storage.

    Args:
        job_id:     The job UUID, used to construct the object key.
        local_path: Absolute or relative path to the compiled PDF on disk.
        client:     A Supabase ``Client`` instance.
        bucket:     The Storage bucket name (e.g. ``"resumes"``).

    Returns:
        The object key that was uploaded (``"{job_id}/resume.pdf"``).
    """
    key = pdf_key(job_id)
    data = Path(local_path).read_bytes()
    client.storage.from_(bucket).upload(key, data, {"upsert": "true"})
    return key


def download_pdf_bytes(
    object_key: str,
    client: Any,
    bucket: str,
) -> bytes | None:
    """Download bytes for *object_key* from Supabase Storage.

    Returns ``None`` if the object does not exist or the download fails.
    """
    try:
        return client.storage.from_(bucket).download(object_key)
    except Exception:
        log.warning("Storage download failed for key %s", object_key)
        return None


def delete_prefix(
    job_id: str,
    client: Any,
    bucket: str,
) -> None:
    """Remove the PDF object for *job_id* from Supabase Storage.

    Tolerates missing objects — silently succeeds if the key doesn't exist.
    """
    try:
        client.storage.from_(bucket).remove([pdf_key(job_id)])
    except Exception:
        log.warning("Storage delete failed for job %s", job_id)
