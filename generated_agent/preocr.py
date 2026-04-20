"""Pre-OCR CLI step — spec 0010 / ADR-0010.

The CLI calls the OCR MCP server directly (via ``mcp.client.sse.sse_client`` +
``ClientSession``) before the ``LlmAgent`` runner starts. The detected exam
names are injected into the prompt as plain text — the image bytes never
reach the model. This removes the probabilistic "LLM fabricates base64"
failure documented in ADR-0010.

Public surface:
    _PreOcrError         — raised on timeout / connection / server errors
    _run_preocr          — async function, returns ``list[str]``
    _build_preocr_prompt — builds a single-text-part ``Content`` for the agent
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

_LOGGER = logging.getLogger(__name__)

_TOOL_NAME = "extract_exams_from_image"
_PROMPT_PREFIX = "EXAMES DETECTADOS (OCR pré-executado pelo CLI):"
_PROMPT_SUFFIX = (
    "Use essa lista como ponto de partida do passo 2 do plano fixo "
    "(search_exam_code em paralelo, etc.)."
)

# Server ToolError message format: "[E_OCR_*] <msg> — <hint>"
_TOOL_ERROR_RE = re.compile(r"\[(E_OCR_[A-Z_]+)\]")


class _PreOcrError(Exception):
    """Raised when the pre-OCR step fails.

    Attributes:
        code: Canonical error code (``E_MCP_UNAVAILABLE`` or any ``E_OCR_*``).
        message: Human-readable message.
        hint: Optional corrective action.
    """

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _extract_exams(result: Any) -> list[str]:
    """Pull ``list[str]`` out of a ``CallToolResult``.

    FastMCP wraps a ``-> list[str]`` tool return in
    ``structuredContent={"result": [...]}``. Tolerate both
    ``structuredContent`` and ``structured_content`` attribute spellings.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)

    if isinstance(structured, dict) and "result" in structured:
        payload = structured["result"]
    else:
        payload = structured

    if payload is None:
        return []
    if isinstance(payload, list):
        return [str(x) for x in payload if isinstance(x, (str, int, float))]
    return []


def _server_error_code(result: Any) -> str | None:
    """Return ``E_OCR_*`` if the tool result carries an error; else ``None``."""
    if not getattr(result, "isError", False):
        return None
    content = getattr(result, "content", []) or []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            match = _TOOL_ERROR_RE.search(text)
            if match:
                return match.group(1)
    return "E_OCR_UNKNOWN"


async def _call_once(
    *,
    image_base64: str,
    correlation_id: str,
    mcp_url: str,
    timeout_s: float,
) -> list[str]:
    """Open an SSE session, call the tool once, return exam list.

    Raises ``_PreOcrError`` on server-side errors; lets asyncio.TimeoutError /
    connection errors bubble to the retry loop in ``_run_preocr``.
    """
    sse_headers = {
        "Accept": "application/json, text/event-stream",
        "X-Correlation-ID": correlation_id,
    }

    async with sse_client(mcp_url, headers=sse_headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                _TOOL_NAME,
                {"image_base64": image_base64},
            )

    err_code = _server_error_code(result)
    if err_code is not None:
        raise _PreOcrError(
            code=err_code,
            message="OCR MCP rejeitou a imagem.",
            hint="Verifique o log do servico ocr-mcp.",
        )

    return _extract_exams(result)


async def _run_preocr(
    image_bytes: bytes,
    correlation_id: str,
    *,
    mcp_url: str,
    timeout_s: float,
    connect_retries: int = 1,
) -> list[str]:
    """Run the pre-OCR step — spec 0010 AC1, AC6, AC7.

    Pre:
        - ``image_bytes`` non-empty (caller validates file existence).
        - ``mcp_url`` is a reachable SSE endpoint.

    Post:
        Returns ``list[str]`` (possibly empty) OR raises ``_PreOcrError``.
        Never silently swallows connection / timeout errors.

    Args:
        image_bytes: Raw image bytes.
        correlation_id: UUID to propagate as ``X-Correlation-ID``.
        mcp_url: Full SSE URL, e.g. ``http://ocr-mcp:8001/sse``.
        timeout_s: Hard timeout wrapping the full SSE session + tool call.
        connect_retries: Number of reconnect attempts on transport errors.
    """
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    sha_prefix = hashlib.sha256(image_bytes).hexdigest()[:8]

    _LOGGER.info(
        "agent.preocr.invoked",
        extra={
            "event": "agent.preocr.invoked",
            "correlation_id": correlation_id,
            "sha256_prefix": sha_prefix,
            "mcp_url": mcp_url,
        },
    )

    last_transport_error: Exception | None = None
    attempts = max(1, connect_retries + 1)
    loop = asyncio.get_running_loop()
    started = loop.time()

    for attempt in range(1, attempts + 1):
        try:
            exams = await asyncio.wait_for(
                _call_once(
                    image_base64=image_base64,
                    correlation_id=correlation_id,
                    mcp_url=mcp_url,
                    timeout_s=timeout_s,
                ),
                timeout=timeout_s,
            )
        except _PreOcrError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            _LOGGER.warning(
                "agent.preocr.timeout",
                extra={
                    "event": "agent.preocr.timeout",
                    "correlation_id": correlation_id,
                    "attempt": attempt,
                    "timeout_s": timeout_s,
                },
            )
            last_transport_error = exc
            # Timeouts do not retry — they indicate the call itself is too slow.
            break
        except Exception as exc:  # noqa: BLE001 — transport layer is broad
            _LOGGER.warning(
                "agent.preocr.transport_error",
                extra={
                    "event": "agent.preocr.transport_error",
                    "correlation_id": correlation_id,
                    "attempt": attempt,
                    "error": str(exc),
                },
            )
            last_transport_error = exc
            if attempt < attempts:
                continue
            break
        else:
            duration_ms = int((loop.time() - started) * 1000)
            _LOGGER.info(
                "agent.preocr.result",
                extra={
                    "event": "agent.preocr.result",
                    "correlation_id": correlation_id,
                    "exam_count": len(exams),
                    "duration_ms": duration_ms,
                },
            )
            return exams

    raise _PreOcrError(
        code="E_MCP_UNAVAILABLE",
        message=f"OCR MCP indisponivel apos {attempts} tentativa(s).",
        hint="Verifique se o servico ocr-mcp esta saudavel (docker compose ps).",
    ) from last_transport_error


def _build_preocr_prompt(exams: list[str]) -> Any:
    """Build a text-only ``Content`` with the exam list — spec 0010 AC3.

    Returns a ``genai_types.Content`` with role=user and exactly one
    ``Part(text=...)``. No ``inline_data`` is attached.
    """
    from google.genai import types as genai_types  # noqa: PLC0415

    exam_json = json.dumps(exams, ensure_ascii=False)
    body = f"{_PROMPT_PREFIX} {exam_json}\n\n{_PROMPT_SUFFIX}"
    return genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=body)],
    )
