"""Entry point for the RAG MCP server.

Start: python -m rag_mcp
Port: 8002 (ADR-0001) — configured on the FastMCP instance in server.py
Transport: SSE

Startup sequence (AC20):
    1. Load catalog from rag_mcp/data/exams.csv
    2. On CatalogError: emit JSON error to stderr, exit(1) — startup abort
    3. On success: start FastMCP SSE server

Health check (AC12):
    HEAD http://localhost:8002/sse → 200 or 405
"""

from __future__ import annotations

import json
import sys

from rag_mcp.errors import CatalogError
from rag_mcp.logging_ import get_logger
from rag_mcp.server import load_catalog, mcp

_logger = get_logger("rag-mcp")


def main() -> None:
    """Load catalog and start the RAG MCP SSE server on port 8002.

    Host/port are configured at FastMCP construction time (server.py).
    In mcp[cli] >= 1.0, `run()` no longer accepts host/port as kwargs.
    """
    # Step 1: Load catalog — abort with exit(1) on failure (AC20)
    try:
        load_catalog()
    except CatalogError as exc:
        # Emit canonical ADR-0008 error shape as single-line JSON on stderr (AC20)
        error_record = {
            "service": "rag-mcp",
            "event": "error.raised",
            "code": exc.code,
            "message": exc.message,
            "hint": exc.hint,
            "context": exc.context,
        }
        print(json.dumps(error_record, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    # Step 2: Start server
    _logger.info(
        "server.starting",
        extra={"port": 8002, "transport": "sse"},
    )
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
