"""Custom exception types for the database persistence layer."""
from __future__ import annotations


class DbError(Exception):
    """Base class for all database layer errors."""


class JobNotFound(DbError):
    """Raised when a job_id lookup returns no result."""
