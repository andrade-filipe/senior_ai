"""Real OCR engine for ocr-mcp — Tesseract via pytesseract + Pillow (spec 0011).

Public API:
    extract_exam_lines(image_bytes, *, lang="por", timeout_s=5.0) -> list[str]

Design:
    - Runs pytesseract.image_to_string() inside asyncio.to_thread() so the event
      loop stays unblocked while Tesseract spawns its subprocess.
    - Applies header-blacklist + length-range + cap-64 filter to raw output.
    - Does NOT apply pii_mask — that is Layer 1 and belongs to server._do_ocr.
    - Does NOT raise ToolError — raises OcrTimeoutError (RuntimeError subclass)
      on timeout; server._do_ocr converts it to ToolError(E_OCR_TIMEOUT).

ADR refs: ADR-0001 (SSE), ADR-0003 (PII Layer 1 in server), ADR-0011 (Tesseract).
"""

from __future__ import annotations

import asyncio
import io
import re
import time
from typing import TypeAlias

# pytesseract and Pillow are runtime deps installed in the Docker image.
# They are optional in the dev environment; import errors surface clearly.
import pytesseract
from PIL import Image

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ExamLine: TypeAlias = str  # post-filtered; NOT post-pii-mask (server does that)

# ---------------------------------------------------------------------------
# Filter constants (plan.md § Data models)
# ---------------------------------------------------------------------------

_MIN_LINE_LEN: int = 3
_MAX_LINE_LEN: int = 120
_MAX_LINES: int = 64

# Regex for header lines to drop (case-insensitive prefix match).
# Pattern matches any of these keywords followed by optional whitespace + colon/：.
_HEADER_RE = re.compile(
    r"^(?:"
    r"paciente|data|m[eé]dico|crm|conv[eê]nio|endere[cç]o"
    r"|telefone|fone|idade|cpf|rg|cl[ií]nica"
    r")\s*[:：]",
    re.IGNORECASE,
)

# Matches lines that are entirely digits (e.g. "12345") or entirely punctuation/spaces.
_ALL_DIGITS_OR_PUNCT_RE = re.compile(r"^[\d\s\W]+$")


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class OcrTimeoutError(RuntimeError):
    """Raised when pytesseract.image_to_string exceeds timeout_s.

    pytesseract raises RuntimeError("Tesseract process timeout") when its
    internal timeout elapses. We re-wrap it here for cleaner caller semantics.
    """


# ---------------------------------------------------------------------------
# Internal filter helper
# ---------------------------------------------------------------------------


def _filter_lines(raw_text: str) -> list[ExamLine]:
    """Apply heuristic filters to raw Tesseract multi-line text.

    Pre:
        raw_text is the string returned by pytesseract.image_to_string().

    Post:
        Each item in the returned list satisfies:
            _MIN_LINE_LEN (3) <= len(item) <= _MAX_LINE_LEN (120)
        No item matches _HEADER_RE (header prefix like "Paciente:").
        No item is composed entirely of digits/punctuation.
        len(result) <= _MAX_LINES (64).

    Args:
        raw_text: Multi-line string from Tesseract.

    Returns:
        Filtered list of candidate exam lines.
    """
    lines: list[ExamLine] = []
    for raw_line in raw_text.split("\n"):
        line = raw_line.strip()

        # Drop empty / whitespace-only
        if not line:
            continue

        # Drop lines shorter than minimum
        if len(line) < _MIN_LINE_LEN:
            continue

        # Drop lines longer than maximum (noise artifacts)
        if len(line) > _MAX_LINE_LEN:
            continue

        # Drop header-like prefixes
        if _HEADER_RE.match(line):
            continue

        # Drop lines that are purely digits or punctuation (e.g. dates, separators)
        if _ALL_DIGITS_OR_PUNCT_RE.match(line):
            continue

        lines.append(line)

        # Cap at maximum line count
        if len(lines) >= _MAX_LINES:
            break

    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_exam_lines(
    image_bytes: bytes,
    *,
    lang: str = "por",
    timeout_s: float = 5.0,
) -> list[ExamLine]:
    """Run OCR on image_bytes and return filtered candidate exam lines.

    Pre:
        image_bytes is a valid PNG/JPEG that Pillow can open.
        timeout_s > 0; lang is a Tesseract language code installed in the image
        (e.g. 'por' for Portuguese, guaranteed in Docker by tesseract-ocr-por).
        image_bytes size <= OCR_IMAGE_MAX_BYTES (caller server._do_ocr validates).

    Post:
        Returns list[str] with at most 64 items.
        Each item satisfies 3 <= len <= 120 chars.
        No item starts with a known header prefix (e.g. "Paciente:").
        Returns [] if zero lines pass the filter (blank/noise image).
        Does NOT apply pii_mask — that is the server layer's responsibility.

    Invariant:
        assert all(_MIN_LINE_LEN <= len(x) <= _MAX_LINE_LEN for x in result)

    Args:
        image_bytes: Raw PNG/JPEG bytes.
        lang: Tesseract language code (default: "por").
        timeout_s: Seconds before aborting Tesseract subprocess.

    Returns:
        Filtered list of candidate exam line strings.

    Raises:
        OcrTimeoutError: Tesseract subprocess exceeded timeout_s.
        pytesseract.TesseractNotFoundError: Tesseract binary not found on PATH.
        pytesseract.TesseractError: Internal Tesseract engine failure.
        PIL.UnidentifiedImageError: image_bytes are not a valid image format.
    """
    # Decode image bytes to PIL.Image — raises PIL.UnidentifiedImageError on bad input.
    buf = io.BytesIO(image_bytes)
    try:
        img = Image.open(buf)
        img.load()  # force decode so the BytesIO stays alive (deterministic close)
    finally:
        buf.close()

    t0 = time.monotonic()

    def _run_tesseract() -> str:
        """Blocking call to pytesseract — runs in a thread pool worker."""
        try:
            return pytesseract.image_to_string(img, lang=lang, timeout=timeout_s)
        except RuntimeError as exc:
            # pytesseract raises RuntimeError("Tesseract process timeout") on timeout.
            msg = str(exc).lower()
            if "timeout" in msg:
                raise OcrTimeoutError(
                    f"Tesseract exceeded {timeout_s}s (lang={lang})"
                ) from exc
            raise

    try:
        raw_text: str = await asyncio.to_thread(_run_tesseract)
    except OcrTimeoutError:
        raise

    duration_ms = (time.monotonic() - t0) * 1000
    _ = duration_ms  # available to callers via logging in server layer

    result = _filter_lines(raw_text)

    # DbC invariant — assert post-condition
    assert all(_MIN_LINE_LEN <= len(x) <= _MAX_LINE_LEN for x in result), (
        f"ocr.extract_exam_lines post-condition violated: "
        f"some lines outside [{_MIN_LINE_LEN}, {_MAX_LINE_LEN}] chars"
    )

    return result
