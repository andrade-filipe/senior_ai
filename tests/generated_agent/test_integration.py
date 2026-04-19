"""Integration tests — all skipped until docker compose is up (Block 0008).

These tests require the MCPs and scheduling API to be running.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_mcp_tool_discovery() -> None:
    """AC6 / T015: agent discovers OCR and RAG tools via MCP protocol."""
    raise NotImplementedError


@pytest.mark.skip(reason="requires docker compose — Bloco 0008")
def test_openapi_tool_registered() -> None:
    """AC7 / T016: POST /api/v1/appointments tool appears in agent tool inventory."""
    raise NotImplementedError
