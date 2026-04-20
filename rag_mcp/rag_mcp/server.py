"""RAG MCP server — FastMCP tool registration and lifecycle.

Tools exposed:
    search_exam_code(exam_name: str) -> ExamMatch | None
    list_exams(limit: int = 100) -> list[ExamSummary]

Transport: SSE on port 8002 (ADR-0001).
Catalog: loaded once at startup from rag_mcp/data/exams.csv (AC6).

Timeout (AC21): asyncio.wait_for with 2 s hard limit on search_exam_code.
    Using asyncio.wait_for() is sufficient because rapidfuzz is pure Python with
    no blocking I/O — the coroutine cooperates naturally.
    multiprocessing.Pool would be overkill for a ~100-entry catalog.

Guardrails (ADR-0008):
    - exam_name > 500 chars → E_RAG_QUERY_TOO_LARGE (AC18)
    - exam_name empty/whitespace → E_RAG_QUERY_EMPTY (AC19)
    - search timeout > 2 s → E_RAG_TIMEOUT (AC21)
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from rag_mcp.catalog import build_choices, load, search
from rag_mcp.errors import RagError
from rag_mcp.logging_ import get_logger
from rag_mcp.models import ExamEntry, ExamMatch, ExamSummary

# Guardrail caps (ADR-0008)
_QUERY_MAX_CHARS = int(os.environ.get("RAG_QUERY_MAX_CHARS", "500"))  # AC18
_SEARCH_TIMEOUT_S = float(os.environ.get("RAG_SEARCH_TIMEOUT_SECONDS", "2"))  # AC21
_CATALOG_PATH = os.environ.get(
    "RAG_CATALOG_PATH",
    str(Path(__file__).parent / "data" / "exams.csv"),
)

logger = get_logger("rag-mcp")

# host/port are read by FastMCP.settings and applied when run(transport="sse")
# binds the SSE server (mcp[cli] >= 1.0 moved these from run() kwargs to the
# constructor). 0.0.0.0 is required inside Docker networking.
mcp = FastMCP("rag-mcp", host="0.0.0.0", port=8002)  # noqa: S104

# ---------------------------------------------------------------------------
# Module-level catalog state — populated in load_catalog()
# ---------------------------------------------------------------------------
_entries: list[ExamEntry] = []
_choices: list[str] = []
_mapping: dict[str, ExamEntry] = {}


def load_catalog(path: Path | None = None) -> None:
    """Load the exam catalog from CSV and populate module state.

    Called once at server startup (see __main__.py).
    Raises CatalogError (→ startup abort) if the CSV is invalid (AC20).

    Args:
        path: Path to the CSV file. Defaults to rag_mcp/data/exams.csv
              relative to this file's package root.

    Raises:
        CatalogError: code='E_CATALOG_LOAD_FAILED' on any load failure.
    """
    global _entries, _choices, _mapping  # noqa: PLW0603

    if path is None:
        path = Path(_CATALOG_PATH)

    logger.info(
        "catalog.loading",
        extra={"path": str(path)},
    )

    _entries = load(path)
    _choices, _mapping = build_choices(_entries)

    logger.info(
        "catalog.loaded",
        extra={
            "entry_count": len(_entries),
            "choice_count": len(_choices),
        },
    )


def _raise_tool_error(err: RagError) -> None:
    """Convert RagError to MCP ToolError and raise.

    Args:
        err: The domain error to convert.

    Raises:
        ToolError: Always.
    """
    raise ToolError(f"[{err.code}] {err.message} — {err.hint}")


@mcp.tool()
async def search_exam_code(exam_name: str) -> ExamMatch | None:
    """Fuzzy search the exam catalog for a canonical code.

    Pre:
        exam_name is a non-empty string (stripped) with <= 500 chars.

    Post:
        Returns ExamMatch with score in [0.0, 1.0] when best rapidfuzz score >= 80/100.
        Returns None when no candidate reaches threshold 80 (AC8, AC13).
        score is never None inside ExamMatch; None return = no match.

    Args:
        exam_name: Exam name to search for (may contain typos/abbreviations).

    Returns:
        ExamMatch(name, code, score) or None.

    Raises:
        ToolError: code E_RAG_QUERY_TOO_LARGE — exam_name > 500 chars (AC18).
        ToolError: code E_RAG_QUERY_EMPTY     — exam_name empty/whitespace (AC19).
        ToolError: code E_RAG_TIMEOUT          — search exceeded 2 s (AC21).
    """
    start_ms = time.monotonic() * 1000

    # Guard: empty/whitespace (AC19) — check before strip to catch whitespace-only
    stripped = exam_name.strip() if exam_name else ""
    if not stripped:
        err = RagError(
            code="E_RAG_QUERY_EMPTY",
            message="`exam_name` está vazia",
            hint="Envie o nome do exame",
        )
        logger.error(
            "tool.failed",
            extra={"tool": "search_exam_code", "error_code": err.code},
        )
        _raise_tool_error(err)
        return None  # unreachable

    # Guard: too long (AC18) — check after confirming non-empty
    if len(exam_name) > _QUERY_MAX_CHARS:
        err = RagError(
            code="E_RAG_QUERY_TOO_LARGE",
            message=f"`exam_name` excede {_QUERY_MAX_CHARS} chars",
            hint="Envie apenas o nome do exame, sem contexto extra",
            context={"chars_received": len(exam_name), "chars_max": _QUERY_MAX_CHARS},
        )
        logger.error(
            "tool.failed",
            extra={
                "tool": "search_exam_code",
                "error_code": err.code,
                "chars_received": len(exam_name),
            },
        )
        _raise_tool_error(err)
        return None  # unreachable

    # Timeout wrapper (AC21) — asyncio.wait_for is sufficient for pure Python rapidfuzz.
    # multiprocessing.Pool (Presidio-style hard-kill) would be overkill for a ~100-entry
    # in-memory catalog; asyncio cooperative cancellation is fine here.
    try:
        result: ExamMatch | None = await asyncio.wait_for(
            _search_async(stripped), timeout=_SEARCH_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        err = RagError(
            code="E_RAG_TIMEOUT",
            message=f"RAG não respondeu em {_SEARCH_TIMEOUT_S} s",
            hint="Verifique se `rag-mcp` está saudável",
            context={"timeout_s": _SEARCH_TIMEOUT_S},
        )
        logger.error(
            "tool.failed",
            extra={"tool": "search_exam_code", "error_code": err.code},
        )
        _raise_tool_error(err)
        return None  # unreachable

    duration_ms = time.monotonic() * 1000 - start_ms
    logger.info(
        "tool.called",
        extra={
            "tool": "search_exam_code",
            "duration_ms": round(duration_ms, 1),
            "matched": result is not None,
        },
    )
    return result


async def _search_async(query: str) -> ExamMatch | None:
    """Async wrapper for the synchronous rapidfuzz search.

    Args:
        query: Already-stripped, size-validated exam name.

    Returns:
        ExamMatch or None.
    """
    return search(query, _choices, _mapping)


@mcp.tool()
async def list_exams(limit: int = 100) -> list[ExamSummary]:
    """Return a paginated list of catalog entries in CSV order.

    Args:
        limit: Maximum number of entries to return (default 100).

    Returns:
        List of ExamSummary(name, code) up to limit items (AC10).
    """
    start_ms = time.monotonic() * 1000

    summaries = [ExamSummary(name=e.name, code=e.code) for e in _entries[:limit]]

    duration_ms = time.monotonic() * 1000 - start_ms
    logger.info(
        "tool.called",
        extra={
            "tool": "list_exams",
            "duration_ms": round(duration_ms, 1),
            "returned": len(summaries),
        },
    )
    return summaries


def get_mcp() -> FastMCP:
    """Return the configured FastMCP instance (for testing).

    Returns:
        The module-level FastMCP instance.
    """
    return mcp


def get_entries() -> list[ExamEntry]:
    """Return loaded catalog entries (for testing).

    Returns:
        Currently loaded ExamEntry list.
    """
    return _entries
