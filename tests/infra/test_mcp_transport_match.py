"""Regression guard: MCP client transport MUST match server transport.

Context: on 2026-04-19 an E2E run hit `POST /sse → HTTP 405 Method Not Allowed`.
Root cause: the agent used `StreamableHTTPConnectionParams` (streamable-http
protocol: one POST endpoint) against FastMCP servers started with
`mcp.run(transport="sse")` (legacy SSE protocol: GET /sse + POST /messages).

Ground truth (ADK 1.31.0, google/adk/tools/mcp_tool/mcp_session_manager.py):
- line 89:  class SseConnectionParams(BaseModel)          — dispatches to sse_client()
- line 120: class StreamableHTTPConnectionParams          — dispatches to streamablehttp_client()
- line 400: isinstance(...SseConnectionParams)            → sse_client
- line 408: isinstance(...StreamableHTTPConnectionParams) → streamablehttp_client

Invariant enforced here: every MCP server in this repo uses transport="sse",
therefore every MCP client (agent + template) MUST import SseConnectionParams
and MUST NOT reference StreamableHTTPConnectionParams.

See also: ai-context/references/DESIGN_AUDIT.md § C2 correction note (2026-04-19).
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

# Servers that must be checked
_MCP_SERVERS = ("ocr_mcp", "rag_mcp")

# Client files that must be checked
_CLIENT_AGENT = REPO_ROOT / "generated_agent" / "agent.py"
_CLIENT_TEMPLATE = REPO_ROOT / "transpiler" / "transpiler" / "templates" / "agent.py.j2"


def _find_transport(text: str) -> str | None:
    """Return the transport literal passed to mcp.run(transport=...), or None."""
    match = re.search(
        r'mcp\.run\s*\(\s*transport\s*=\s*["\']([a-z\-]+)["\']',
        text,
    )
    return match.group(1) if match else None


@pytest.mark.parametrize("server", _MCP_SERVERS)
def test_servers_use_sse_transport(server: str) -> None:
    """Every MCP server __main__ must call mcp.run(transport='sse').

    Changing this breaks the contract with SseConnectionParams on the client
    side and will regress the 405 bug.
    """
    main_py = REPO_ROOT / server / server / "__main__.py"
    assert main_py.exists(), f"{server}/__main__.py missing"
    transport = _find_transport(main_py.read_text(encoding="utf-8"))
    assert transport == "sse", (
        f"{server} must use mcp.run(transport='sse'); found {transport!r}. "
        "Switching to streamable-http requires also switching the clients to "
        "StreamableHTTPConnectionParams AND updating this guard."
    )


def test_generated_agent_uses_sse_connection_params() -> None:
    """generated_agent/agent.py imports SseConnectionParams, never Streamable."""
    text = _CLIENT_AGENT.read_text(encoding="utf-8")
    assert "SseConnectionParams" in text, (
        "generated_agent/agent.py must import SseConnectionParams "
        "(FastMCP transport='sse' requires it)."
    )
    assert "StreamableHTTPConnectionParams" not in text, (
        "generated_agent/agent.py must NOT reference "
        "StreamableHTTPConnectionParams — causes HTTP 405 against SSE server."
    )


def test_template_uses_sse_connection_params() -> None:
    """transpiler agent.py.j2 emits SseConnectionParams, never Streamable."""
    text = _CLIENT_TEMPLATE.read_text(encoding="utf-8")
    assert "SseConnectionParams" in text, (
        "agent.py.j2 must emit SseConnectionParams so generated agents are "
        "compatible with FastMCP transport='sse' servers."
    )
    assert "StreamableHTTPConnectionParams" not in text, (
        "agent.py.j2 must NOT emit StreamableHTTPConnectionParams — "
        "regression would propagate the 405 bug to every regenerated agent."
    )
