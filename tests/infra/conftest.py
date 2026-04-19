"""Shared fixtures for infra tests.

All yaml/regex tests run in the normal test suite (no Docker needed).
Tests marked @pytest.mark.infra require a running Docker daemon and are
skipped by default (pass -m infra to enable).
"""

from __future__ import annotations

import pathlib

import pytest

# Repo root — all paths are relative to this
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so pytest does not emit PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "infra: mark test as requiring a Docker daemon (skipped in unit pass)",
    )
