"""Shared pytest configuration for web route tests."""
import pytest


def pytest_configure(config):
    """Register custom marks so -m integration works cleanly."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require external tools like tectonic)",
    )
