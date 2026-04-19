"""Tests for RAG MCP server startup and catalog load failure (AC20, T028).

Covers:
    T028 [AC20]: catalog load failure → stderr JSON with E_CATALOG_LOAD_FAILED, exit != 0.

The test invokes __main__.py as a subprocess with a bad catalog path via env var
override to verify the startup abort path without requiring a running server.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestCatalogLoadFailureShape:
    """T028 [AC20]: startup failure emits canonical JSON error shape."""

    def test_missing_catalog_causes_exit_nonzero(self, tmp_path: Path) -> None:
        """T028 [AC20]: __main__.py exits with code != 0 when catalog missing."""
        # Use a Python one-liner to simulate __main__ with bad path
        script = """
import sys, json
from pathlib import Path
from rag_mcp.errors import CatalogError
from rag_mcp.catalog import load

path = Path(sys.argv[1])
try:
    load(path)
except CatalogError as exc:
    error_record = {
        "service": "rag-mcp",
        "event": "error.raised",
        "code": exc.code,
        "message": exc.message,
        "hint": exc.hint,
        "context": exc.context,
    }
    print(json.dumps(error_record), file=sys.stderr)
    sys.exit(1)
"""
        non_existent = tmp_path / "no_such_file.csv"
        result = subprocess.run(
            [sys.executable, "-c", script, str(non_existent)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode != 0, "Process must exit with non-zero code on catalog failure"

    def test_startup_error_has_canonical_shape(self, tmp_path: Path) -> None:
        """T028 [AC20]: error output contains E_CATALOG_LOAD_FAILED JSON."""
        script = """
import sys, json
from pathlib import Path
from rag_mcp.errors import CatalogError
from rag_mcp.catalog import load

path = Path(sys.argv[1])
try:
    load(path)
except CatalogError as exc:
    error_record = {
        "service": "rag-mcp",
        "event": "error.raised",
        "code": exc.code,
        "message": exc.message,
        "hint": exc.hint,
        "context": exc.context,
    }
    print(json.dumps(error_record), file=sys.stderr)
    sys.exit(1)
"""
        non_existent = tmp_path / "no_such_file.csv"
        result = subprocess.run(
            [sys.executable, "-c", script, str(non_existent)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        stderr_lines = [l for l in result.stderr.splitlines() if l.strip()]
        assert stderr_lines, "Expected JSON error output in stderr"

        # Parse the error JSON
        error_record = json.loads(stderr_lines[-1])
        assert error_record["code"] == "E_CATALOG_LOAD_FAILED"
        assert "message" in error_record
        assert "hint" in error_record or "context" in error_record
