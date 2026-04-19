"""Entry point for the OCR MCP server.

Start: python -m ocr_mcp
Port: 8001 (ADR-0001) — configured on the FastMCP instance in server.py
Transport: SSE

Health check (AC12):
    HEAD http://localhost:8001/sse → 200 or 405
    (FastMCP/Starlette responds to HEAD; suffices for compose service_started)
"""

from __future__ import annotations

from ocr_mcp.logging_ import get_logger
from ocr_mcp.server import mcp

_logger = get_logger("ocr-mcp")


def main() -> None:
    """Start the OCR MCP SSE server on port 8001.

    Host/port are configured at FastMCP construction time (server.py).
    In mcp[cli] >= 1.0, `run()` no longer accepts host/port as kwargs.
    """
    _logger.info(
        "server.starting",
        extra={"port": 8001, "transport": "sse"},
    )
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
