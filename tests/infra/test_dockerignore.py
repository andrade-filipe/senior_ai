"""Infra tests — .dockerignore compliance (AC4, AC13).

All tests read the .dockerignore file — no Docker daemon required.
"""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"

# Entries that MUST appear in .dockerignore (AC4 + AC13)
REQUIRED_EXCLUSIONS = [
    ".venv",
    "__pycache__",
    "tests/",
    ".git",
    "docs/",
    ".env",
]


def _read_dockerignore() -> str:
    """Read .dockerignore; fail clearly if missing."""
    assert DOCKERIGNORE_PATH.exists(), (
        f".dockerignore not found at {DOCKERIGNORE_PATH}. "
        "Create it to prevent secrets and bloat from entering build context."
    )
    return DOCKERIGNORE_PATH.read_text(encoding="utf-8")


class TestDockerignoreAC4:
    """[AC4] .dockerignore excludes dev/test artefacts."""

    @pytest.mark.parametrize("entry", [".venv", "__pycache__", "tests/", ".git", "docs/"])
    def test_dockerignore_excludes_dev_artifacts(self, entry: str) -> None:
        content = _read_dockerignore()
        # Allow glob variants (e.g. "**/.venv/" also covers ".venv")
        assert entry.rstrip("/") in content, (
            f"[AC4] .dockerignore must exclude '{entry}' "
            "(prevents bloating image build context)."
        )


class TestDockerignoreAC13:
    """[AC13] .dockerignore excludes .env to prevent embedding secrets in image."""

    def test_dockerignore_excludes_env(self) -> None:
        content = _read_dockerignore()
        # Must have ".env" as an exclusion; "!.env.example" (negation) is allowed
        # but the base ".env" or ".env.*" must appear as an exclusion pattern.
        lines = [line.strip() for line in content.splitlines()]
        env_exclusion = any(
            line in (".env", ".env.*", "**/.env", "**/.env.*")
            for line in lines
            if not line.startswith("!")
        )
        assert env_exclusion, (
            "[AC13] .dockerignore must exclude '.env' (or '.env.*') to prevent "
            "secrets from being embedded in the image build context."
        )
