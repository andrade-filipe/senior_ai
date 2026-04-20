"""OCR MCP server — FastMCP tool registration and lifecycle.

Tool exposed:
    extract_exams_from_image(image_base64: str) -> list[str]

Transport: SSE on port 8001 (ADR-0001).
PII: security.pii_mask() applied on every return path (ADR-0003 line 1, AC4).

Timeout (AC17): asyncio.wait_for with 5 s hard limit.
    Using asyncio.wait_for() is sufficient because the OCR body is a pure Python
    dict lookup (no blocking I/O) — the coroutine cooperates naturally.
    multiprocessing.Pool (Presidio-style) would be overkill here.

Guardrails (ADR-0008):
    - image_base64 decoded > 5 MB → E_OCR_IMAGE_TOO_LARGE (AC15)
    - invalid base64 → E_OCR_INVALID_INPUT (AC16)
    - timeout > 5 s → E_OCR_TIMEOUT (AC17)
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import os
import time

from mcp.server.fastmcp import FastMCP
# ToolError is the standard way to signal tool failures in FastMCP (mcp[cli] >= 1.0)
# If this import fails, check: https://github.com/modelcontextprotocol/python-sdk
from mcp.server.fastmcp.exceptions import ToolError

from ocr_mcp import fixtures, ocr
from ocr_mcp.errors import OcrError
from ocr_mcp.logging_ import get_logger
from ocr_mcp.ocr import OcrTimeoutError as _OcrTimeoutError

# Guardrail caps (ADR-0008 § Guardrails de tamanho)
_IMAGE_MAX_BYTES = int(os.environ.get("OCR_IMAGE_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB decoded
_OCR_TIMEOUT_S = float(os.environ.get("OCR_TIMEOUT_SECONDS", "5"))  # AC17
_DEFAULT_LANGUAGE = os.environ.get("OCR_DEFAULT_LANGUAGE", "pt")
# Tesseract language code (spec 0011, ADR-0009).
# Separate from OCR_DEFAULT_LANGUAGE which controls the PII mask language.
_TESSERACT_LANG = os.environ.get("OCR_TESSERACT_LANG", "por")

logger = get_logger("ocr-mcp")

# host/port are read by FastMCP.settings and applied when run(transport="sse")
# binds the SSE server (mcp[cli] >= 1.0 moved these from run() kwargs to the
# constructor). 0.0.0.0 is required inside Docker networking.
mcp = FastMCP("ocr-mcp", host="0.0.0.0", port=8001)  # noqa: S104


def _raise_tool_error(err: OcrError) -> None:
    """Convert OcrError to MCP ToolError and raise.

    MCP clients receive the code and message through the ToolError mechanism.

    Args:
        err: The domain error to convert.

    Raises:
        ToolError: Always.
    """
    raise ToolError(f"[{err.code}] {err.message} — {err.hint}")


async def _do_ocr(image_base64: str) -> list[str]:
    """Orchestrate fixture fast-path + real OCR + PII Layer 1.

    Pre:
        image_base64 is a valid base64 string and decoded bytes <= 5 MB.
        (validated by the caller extract_exams_from_image before calling this)

    Post:
        Return value has passed through security.pii_mask() — no raw PII.
        Delegates to real OCR (ocr.extract_exam_lines) only on fixture miss.

    Args:
        image_base64: Valid, size-checked base64 string.

    Returns:
        List of exam names with PII masked.
    """
    from security import pii_mask  # noqa: PLC0415 — avoids import-time side effects

    # --- Fast-path: SHA-256 fixture cache (spec 0011 AC1) ---
    raw_exams = fixtures.lookup(image_base64)

    if raw_exams is not None:
        # Cache hit — log and skip Tesseract entirely.
        logger.info(
            "ocr.lookup.hit",
            extra={"event": "ocr.lookup.hit"},
        )
    else:
        # Cache miss — delegate to real Tesseract OCR (spec 0011 AC2).
        logger.info(
            "ocr.lookup.miss",
            extra={"event": "ocr.lookup.miss"},
        )
        image_bytes = base64.b64decode(image_base64, validate=True)
        byte_size = len(image_bytes)

        t_start = time.monotonic()
        logger.info(
            "ocr.tesseract.invoked",
            extra={
                "event": "ocr.tesseract.invoked",
                "image_size": byte_size,
                "lang": _TESSERACT_LANG,
            },
        )

        try:
            raw_exams = await ocr.extract_exam_lines(
                image_bytes,
                lang=_TESSERACT_LANG,
                timeout_s=_OCR_TIMEOUT_S,
            )
        except _OcrTimeoutError:
            logger.error(
                "ocr.tesseract.timeout",
                extra={"event": "ocr.tesseract.timeout", "lang": _TESSERACT_LANG},
            )
            # Convert Tesseract-internal timeout to asyncio.TimeoutError so that
            # the outer asyncio.wait_for in extract_exams_from_image can handle it
            # uniformly and emit E_OCR_TIMEOUT. Both paths (asyncio cancel + Tesseract
            # subprocess timeout) result in ToolError(E_OCR_TIMEOUT) to the caller.
            raise asyncio.TimeoutError from None

        duration_ms = (time.monotonic() - t_start) * 1000
        logger.info(
            "ocr.tesseract.result",
            extra={
                "event": "ocr.tesseract.result",
                "filtered_line_count": len(raw_exams),
                "duration_ms": round(duration_ms, 1),
                "lang": _TESSERACT_LANG,
            },
        )

    # Apply PII mask item by item (Layer 1 — ADR-0003, AC3).
    # pii_mask runs Presidio under multiprocessing.Pool (blocking call); wrap
    # in asyncio.to_thread so the outer asyncio.wait_for timeout can actually
    # preempt it. Without this, a stuck pool call would not honor AC17.
    masked_names: list[str] = []
    for name in raw_exams:
        result = await asyncio.to_thread(pii_mask, name, language=_DEFAULT_LANGUAGE)
        masked_names.append(result.masked_text)

    return masked_names


@mcp.tool()
async def extract_exams_from_image(image_base64: str) -> list[str]:
    """Extract exam names from a base64-encoded medical order image.

    Returns a deterministic list of exam names based on the image SHA-256 hash.
    Unknown images return an empty list.  All output passes through
    security.pii_mask() before being returned (ADR-0003 line 1, AC4).

    Pre:
        image_base64 must be a non-empty valid RFC 4648 base64 string.
        Decoded size must be <= 5 MB (AC15).

    Post:
        Every string in the returned list has been processed by pii_mask().
        No raw PII value is present in the output (AC4).

    Args:
        image_base64: Base64-encoded PNG/JPEG bytes of the medical order image.

    Returns:
        List of exam name strings (may be empty for unknown images).

    Raises:
        ToolError: code E_OCR_INVALID_INPUT  — image_base64 is invalid base64 (AC16).
        ToolError: code E_OCR_IMAGE_TOO_LARGE — decoded bytes exceed 5 MB (AC15).
        ToolError: code E_OCR_TIMEOUT         — processing exceeded 5 s (AC17).
    """
    start_ms = time.monotonic() * 1000

    # Guard: empty or non-string input (AC16)
    if not image_base64 or not image_base64.strip():
        err = OcrError(
            code="E_OCR_INVALID_INPUT",
            message="`image_base64` não é base64 válido",
            hint="Codifique a imagem em base64 padrão (RFC 4648)",
        )
        logger.error(
            "tool.failed",
            extra={"tool": "extract_exams_from_image", "error_code": err.code},
        )
        _raise_tool_error(err)

    # Guard: decode to check validity and size (AC15, AC16)
    try:
        decoded = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        err = OcrError(
            code="E_OCR_INVALID_INPUT",
            message="`image_base64` não é base64 válido",
            hint="Codifique a imagem em base64 padrão (RFC 4648)",
        )
        logger.error(
            "tool.failed",
            extra={"tool": "extract_exams_from_image", "error_code": err.code},
        )
        _raise_tool_error(err)
        return []  # unreachable; satisfies type checker

    byte_size = len(decoded)
    if byte_size > _IMAGE_MAX_BYTES:
        err = OcrError(
            code="E_OCR_IMAGE_TOO_LARGE",
            message="Imagem > 5 MB não suportada",
            hint="Comprima ou reduza a imagem antes de enviar",
            context={"bytes_received": byte_size, "bytes_max": _IMAGE_MAX_BYTES},
        )
        logger.error(
            "tool.failed",
            extra={
                "tool": "extract_exams_from_image",
                "error_code": err.code,
                "bytes_received": byte_size,
                "bytes_max": _IMAGE_MAX_BYTES,
            },
        )
        _raise_tool_error(err)
        return []  # unreachable

    # Spec 0009 T041: instrument digest of the decoded payload the MCP tool
    # actually received. Compared with the on-disk fixture hash during E2E
    # triage, this distinguishes "agent re-encoded the image" from "agent
    # passed the raw bytestream" as the cause of lookup misses.
    digest = hashlib.sha256(decoded).hexdigest()
    logger.info(
        "ocr.lookup.hash",
        extra={
            "event": "ocr.lookup.hash",
            "tool": "extract_exams_from_image",
            "sha256": digest,
            "sha256_prefix": digest[:12],
            "payload_bytes": byte_size,
        },
    )

    # Timeout wrapper (AC17) — asyncio.wait_for is sufficient for pure Python lookup
    # (no blocking I/O); multiprocessing.Pool would be overkill here.
    try:
        result: list[str] = await asyncio.wait_for(
            _do_ocr(image_base64), timeout=_OCR_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        err = OcrError(
            code="E_OCR_TIMEOUT",
            message=f"OCR não respondeu em {_OCR_TIMEOUT_S} s",
            hint="Verifique se `ocr-mcp` está saudável (`docker compose ps`)",
            context={"timeout_s": _OCR_TIMEOUT_S},
        )
        logger.error(
            "tool.failed",
            extra={"tool": "extract_exams_from_image", "error_code": err.code},
        )
        _raise_tool_error(err)
        return []  # unreachable

    duration_ms = time.monotonic() * 1000 - start_ms
    logger.info(
        "tool.called",
        extra={
            "tool": "extract_exams_from_image",
            "duration_ms": round(duration_ms, 1),
            "exam_count": len(result),
        },
    )
    return result


def get_mcp() -> FastMCP:
    """Return the configured FastMCP instance (for testing).

    Returns:
        The module-level FastMCP instance.
    """
    return mcp
