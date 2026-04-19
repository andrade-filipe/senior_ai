"""Tests for transpiler CLI — python -m transpiler <spec.json> [-o <dir>].

Each test maps to one Acceptance Criterion from
docs/specs/0002-transpiler-mvp/spec.md.

Run:
    uv run pytest transpiler/tests/test_cli.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from transpiler.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_spec(tmp_path: Path, spec: dict[str, Any]) -> Path:
    """Write a spec dict to a temp JSON file; return its Path."""
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p


def _minimal_spec_dict(
    name: str = "my-agent",
    pii_enabled: bool = True,
) -> dict[str, Any]:
    """Return a minimal valid spec dict for CLI tests."""
    return {
        "name": name,
        "description": "Test agent",
        "model": "gemini-2.5-flash",
        "instruction": "Help the user.",
        "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
        "http_tools": [],
        "guardrails": {"pii": {"enabled": pii_enabled, "allow_list": []}},
    }


# ---------------------------------------------------------------------------
# AC4 — Invalid spec: exit code 1, stderr contains E_TRANSPILER_SCHEMA
# T013 [P]
# ---------------------------------------------------------------------------


def test_cli_exits_1_on_schema_error(tmp_path: Path) -> None:
    """AC4 — invalid spec.json (bad model value) causes exit code 1 and stderr
    with code=E_TRANSPILER_SCHEMA.
    """
    bad_spec = _minimal_spec_dict()
    bad_spec["model"] = "gpt-4"  # not in Literal allowlist
    spec_path = _write_spec(tmp_path, bad_spec)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "transpiler", str(spec_path), "-o", str(out_dir)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 1
    assert "E_TRANSPILER_SCHEMA" in result.stderr


# ---------------------------------------------------------------------------
# AC1 / Happy path — exit code 0, generated_agent/ created
# ---------------------------------------------------------------------------


def test_cli_happy_path_exit_0(tmp_path: Path) -> None:
    """AC1 (CLI) — valid spec produces exit code 0 and generated_agent/ directory."""
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "transpiler", str(spec_path), "-o", str(out_dir)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    dest = out_dir / "generated_agent"
    assert dest.is_dir()
    assert (dest / "agent.py").exists()


# ---------------------------------------------------------------------------
# AC11 — Path traversal rejected: exit code 2, stderr E_TRANSPILER_RENDER
# T033 [P] [DbC] — render.Pre (output_dir within cwd)
# ---------------------------------------------------------------------------


def test_output_dir_path_traversal_rejected_relative(tmp_path: Path) -> None:
    """AC11 [DbC render.Pre] — relative path traversal (../../etc) is rejected
    with exit code 2 and E_TRANSPILER_RENDER in stderr.
    """
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())

    result = subprocess.run(
        [sys.executable, "-m", "transpiler", str(spec_path), "-o", "../../etc"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 2
    assert "E_TRANSPILER_RENDER" in result.stderr
    assert "output_dir fora do projeto" in result.stderr


def test_output_dir_path_traversal_rejected_absolute(tmp_path: Path) -> None:
    """AC11 [DbC render.Pre] — absolute path outside cwd (/etc or C:\\Windows)
    is rejected with exit code 2 and E_TRANSPILER_RENDER in stderr.
    """
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())

    # Use an absolute path that is definitely outside tmp_path
    outside = "C:\\Windows\\System32" if os.name == "nt" else "/etc"

    result = subprocess.run(
        [sys.executable, "-m", "transpiler", str(spec_path), "-o", outside],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 2
    assert "E_TRANSPILER_RENDER" in result.stderr


# ---------------------------------------------------------------------------
# CLI --help smoke test
# ---------------------------------------------------------------------------


def test_cli_help_exits_0(tmp_path: Path) -> None:
    """--help exits with code 0 and includes usage information."""
    result = subprocess.run(
        [sys.executable, "-m", "transpiler", "--help"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert "spec.json" in result.stdout.lower() or "transpiler" in result.stdout.lower()


# ---------------------------------------------------------------------------
# CLI --verbose flag produces extra output
# ---------------------------------------------------------------------------


def test_cli_verbose_lists_generated_files(tmp_path: Path) -> None:
    """--verbose flag prints the generated files to stdout."""
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "transpiler", str(spec_path), "-o", str(out_dir), "-v"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    assert "agent.py" in result.stdout


# ---------------------------------------------------------------------------
# main() function unit tests (without subprocess)
# ---------------------------------------------------------------------------


def test_main_returns_0_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() returns 0 for a valid spec and output dir."""
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Change cwd so output dir resolves within it
    monkeypatch.chdir(tmp_path)

    exit_code = main([str(spec_path), "-o", str(out_dir)])
    assert exit_code == 0


def test_main_returns_1_on_schema_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() returns 1 when spec fails Pydantic validation."""
    bad = _minimal_spec_dict()
    bad["model"] = "invalid-model"
    spec_path = _write_spec(tmp_path, bad)

    monkeypatch.chdir(tmp_path)
    exit_code = main([str(spec_path)])
    assert exit_code == 1


def test_main_returns_2_on_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() returns 2 when --output is a path outside cwd."""
    spec_path = _write_spec(tmp_path, _minimal_spec_dict())

    monkeypatch.chdir(tmp_path)
    exit_code = main([str(spec_path), "-o", "../../etc"])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# Stderr line-by-line format (ADR-0008 canonical shape)
# ---------------------------------------------------------------------------


def test_stderr_has_canonical_error_shape(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error output has one line per canonical field (code, message, hint)."""
    bad = _minimal_spec_dict()
    bad["model"] = "wrong-model"
    spec_path = _write_spec(tmp_path, bad)

    monkeypatch.chdir(tmp_path)
    main([str(spec_path)])

    captured = capsys.readouterr()
    stderr_lines = captured.err.splitlines()
    line_keys = [line.split(":")[0].strip() for line in stderr_lines if ":" in line]

    assert "code" in line_keys
    assert "message" in line_keys
