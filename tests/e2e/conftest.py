"""E2E test configuration and shared fixtures.

Provides:
  - DOCKER_BIN / COMPOSE_BIN  — override via env-var DOCKER_BIN so CI can
    point to /usr/bin/docker while local Windows uses the full installer path.
  - wait_for_healthy(url, timeout) — polls until HTTP 200 or TimeoutError.
  - compose_stack (session fixture) — docker compose up/down lifecycle.
  - collect_compose_logs(service) — capture logs from a running compose stack.

Markers registered here (via pytest_configure) are also referenced from
scheduling_api/pyproject.toml [tool.pytest.ini_options].markers.
The two registrations are intentionally redundant: pytest deduplicates them
and this conftest ensures markers work when tests/e2e is discovered without
the scheduling_api pyproject (e.g. pytest tests/e2e --no-header).
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Generator

import httpx
import pytest

# ---------------------------------------------------------------------------
# Docker binary — override via env so CI can use /usr/bin/docker
# ---------------------------------------------------------------------------
# On Windows, subprocess.run() requires Windows-style paths (C:\...) not
# Unix-style paths (/c/...).  We resolve the correct path automatically.
# The DOCKER_BIN env var can always be set to override (CI uses /usr/bin/docker).
import sys as _sys

def _default_docker_bin() -> str:
    """Return the correct docker binary path for the current OS."""
    env_override = os.environ.get("DOCKER_BIN")
    if env_override:
        return env_override
    if _sys.platform == "win32":
        return r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    # Unix default (CI)
    return "/usr/bin/docker"

DOCKER_BIN: str = _default_docker_bin()

# Derive compose command from docker binary (docker compose v2 subcommand)
COMPOSE_BIN: list[str] = [DOCKER_BIN, "compose"]

# Repo root for building paths to docker-compose.yml
import pathlib
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register e2e markers so pytest does not emit PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "e2e_ci: compose + healthchecks + service suites without real Gemini call",
    )
    config.addinivalue_line(
        "markers",
        "e2e_full: full manual E2E with real Gemini call (not run in CI by default)",
    )


# ---------------------------------------------------------------------------
# Helper: wait for a service to become healthy
# ---------------------------------------------------------------------------


def wait_for_healthy(url: str, timeout: float = 60.0) -> None:
    """Poll ``url`` every 1 s until HTTP 200 is returned or ``timeout`` expires.

    Pre:  url is a valid HTTP URL; timeout > 0.
    Post: function returns normally when status_code == 200.
    Raises:
        TimeoutError: when ``timeout`` seconds elapse without a 200 response.
    """
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(1.0)
    raise TimeoutError(
        f"Service at {url!r} did not return 200 within {timeout:.0f}s. "
        f"Last exception: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Helper: collect compose logs
# ---------------------------------------------------------------------------


def collect_compose_logs(service: str | None = None) -> str:
    """Return stdout of ``docker compose logs [service]``.

    Args:
        service: Optional service name.  When None, logs all services.

    Returns:
        Combined stdout string from compose logs command.
    """
    cmd = [*COMPOSE_BIN, "logs", "--no-log-prefix"]
    if service is not None:
        cmd.append(service)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Session fixture: bring compose stack up and tear it down
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def compose_stack() -> Generator[None, None, None]:
    """Start ocr-mcp, rag-mcp, scheduling-api via docker compose.

    Session-scoped: the stack starts once per pytest session and is torn down
    in the finally block regardless of test outcomes.

    Pre:  DOCKER_BIN resolves to a working docker executable.
    Post: scheduling-api /health returns 200 before yielding.
    Teardown: docker compose down -v always runs (idempotent even on failure).
    """
    subprocess.run(
        [
            *COMPOSE_BIN,
            "up",
            "-d",
            "ocr-mcp",
            "rag-mcp",
            "scheduling-api",
        ],
        check=True,
        cwd=str(REPO_ROOT),
    )
    try:
        wait_for_healthy("http://localhost:8000/health", timeout=60.0)
        yield
    finally:
        subprocess.run(
            [*COMPOSE_BIN, "down", "-v"],
            check=False,
            cwd=str(REPO_ROOT),
        )
