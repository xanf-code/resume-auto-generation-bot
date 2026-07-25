"""Tests for Supabase Storage helpers - uses a fully mocked client."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from src.db.storage import delete_prefix, download_pdf_bytes, pdf_key, upload_pdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(bucket: str = "resumes") -> MagicMock:
    return MagicMock()


def _mock_bucket(client: MagicMock, bucket: str = "resumes") -> MagicMock:
    return client.storage.from_.return_value


# ---------------------------------------------------------------------------
# Test: pdf_key returns correct key format
# ---------------------------------------------------------------------------

def test_pdf_key_format():
    key = pdf_key("abc-123")
    assert key == "abc-123/resume.pdf"


# ---------------------------------------------------------------------------
# Test: upload_pdf reads file bytes and calls upload
# ---------------------------------------------------------------------------

def test_upload_pdf_reads_file_and_calls_upload():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.upload.return_value = MagicMock()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test content")
        pdf_path = f.name

    try:
        result = upload_pdf("job-123", pdf_path, client, "resumes")

        client.storage.from_.assert_called_with("resumes")
        bucket_mock.upload.assert_called_once()
        upload_args = bucket_mock.upload.call_args
        # First positional arg is key, second is bytes, options may vary
        call_kwargs = upload_args[1] if upload_args[1] else {}
        call_args = upload_args[0]
        assert call_args[0] == "job-123/resume.pdf"
        assert b"%PDF-1.4" in call_args[1]
        assert result == "job-123/resume.pdf"
    finally:
        os.unlink(pdf_path)


def test_upload_pdf_passes_upsert_true():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.upload.return_value = MagicMock()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"pdf")
        pdf_path = f.name

    try:
        upload_pdf("job-xyz", pdf_path, client, "resumes")
        upload_call = bucket_mock.upload.call_args
        # Check that upsert=True is passed (either as kwarg or in file_options)
        call_kwargs = upload_call[1]
        call_args = upload_call[0]
        # upsert can be in kwargs or as third positional arg (file_options dict)
        # supabase-py accepts "true" string or True bool
        third_arg = call_args[2] if len(call_args) > 2 else {}
        upsert_val = (
            call_kwargs.get("upsert")
            or (isinstance(third_arg, dict) and third_arg.get("upsert"))
        )
        assert upsert_val in (True, "true", "True")
    finally:
        os.unlink(pdf_path)


def test_upload_pdf_returns_correct_key():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.upload.return_value = MagicMock()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"pdf")
        pdf_path = f.name

    try:
        result = upload_pdf("unique-job-id", pdf_path, client, "resumes")
        assert result == "unique-job-id/resume.pdf"
    finally:
        os.unlink(pdf_path)


# ---------------------------------------------------------------------------
# Test: download_pdf_bytes returns bytes
# ---------------------------------------------------------------------------

def test_download_pdf_bytes_calls_download_and_returns_bytes():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.download.return_value = b"%PDF-1.4 some bytes"

    result = download_pdf_bytes("job-123/resume.pdf", client, "resumes")

    client.storage.from_.assert_called_with("resumes")
    bucket_mock.download.assert_called_with("job-123/resume.pdf")
    assert result == b"%PDF-1.4 some bytes"


def test_download_pdf_bytes_returns_none_on_error():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.download.side_effect = Exception("not found")

    result = download_pdf_bytes("missing/resume.pdf", client, "resumes")

    assert result is None


# ---------------------------------------------------------------------------
# Test: delete_prefix removes object from bucket
# ---------------------------------------------------------------------------

def test_delete_prefix_calls_remove_with_correct_key():
    client = _mock_client()
    bucket_mock = _mock_bucket(client)
    bucket_mock.remove.return_value = MagicMock()

    delete_prefix("job-abc", client, "resumes")

    client.storage.from_.assert_called_with("resumes")
    bucket_mock.remove.assert_called_with(["job-abc/resume.pdf"])
