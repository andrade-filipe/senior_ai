"""Snapshot tests for the transpiler — AC9.

Uses pytest-regressions (data_regression) to compare generated file contents
against golden snapshots stored alongside this file (pytest-regressions default).

First-run / regen workflow (T029):
    uv run pytest transpiler/tests/test_snapshots.py --force-regen
    # review generated .yml files, commit them

Normal CI run (after snapshots are committed):
    uv run pytest transpiler/tests/test_snapshots.py -v

Run:
    uv run pytest transpiler/tests/test_snapshots.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from transpiler import load_spec, render

# ---------------------------------------------------------------------------
# Canonical example spec (matches conftest.py spec_example_dict)
# ---------------------------------------------------------------------------

_EXAMPLE_SPEC: dict[str, Any] = {
    "name": "medical-order-agent",
    "description": "Agente de agendamento de exames a partir de pedidos médicos",
    "model": "gemini-2.5-flash",
    "instruction": "Você recebe uma imagem...",
    "mcp_servers": [
        {"name": "ocr", "url": "http://ocr-mcp:8001/sse"},
        {"name": "rag", "url": "http://rag-mcp:8002/sse"},
    ],
    "http_tools": [
        {
            "name": "scheduling",
            "base_url": "http://scheduling-api:8000",
            "openapi_url": "http://scheduling-api:8000/openapi.json",
        }
    ],
    "guardrails": {"pii": {"enabled": True, "allow_list": []}},
}

_NO_PII_SPEC: dict[str, Any] = {
    "name": "no-pii-agent",
    "description": "Agent without PII guard",
    "model": "gemini-2.5-flash",
    "instruction": "Help the user directly.",
    "mcp_servers": [{"name": "ocr", "url": "http://ocr-mcp:8001/sse"}],
    "http_tools": [],
    "guardrails": {"pii": {"enabled": False, "allow_list": []}},
}


def _render_spec(spec_dict: dict[str, Any]) -> dict[str, str]:
    """Render spec_dict to a temp dir and return {filename: content} dict."""
    spec = load_spec(spec_dict)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp)
        render(spec, out_path)
        dest = out_path / "generated_agent"
        return {f.name: f.read_text(encoding="utf-8") for f in sorted(dest.iterdir())}


# ---------------------------------------------------------------------------
# AC9 — Snapshot test via data_regression
# T018 [P]
# ---------------------------------------------------------------------------


@pytest.mark.snapshot
def test_example_snapshot(data_regression: Any) -> None:
    """AC9 — generated package from spec.example matches the golden snapshot.

    First run (or ``--force-regen``): creates/updates the golden snapshot.
    Subsequent runs: fail on any content change (diff must be empty).

    To seed on first run: uv run pytest tests/test_snapshots.py --force-regen
    Then commit the generated .yml files (T029).
    """
    snapshot = _render_spec(_EXAMPLE_SPEC)
    data_regression.check(snapshot)


@pytest.mark.snapshot
def test_no_pii_snapshot(data_regression: Any) -> None:
    """Snapshot for spec without PII guard — verifies determinism across variants."""
    snapshot = _render_spec(_NO_PII_SPEC)
    data_regression.check(snapshot)
