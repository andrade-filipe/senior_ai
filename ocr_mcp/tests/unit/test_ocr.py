"""RED tests for ocr_mcp.ocr module — T010, T011, T015 [DbC].

These tests MUST FAIL until ocr_mcp/ocr_mcp/ocr.py is implemented (Onda C/GREEN).

Design decision (import strategy):
    pytesseract and Pillow are not yet runtime dependencies (Onda C adds them).
    In T010/T011 we mock `pytesseract.image_to_string` entirely — real Tesseract
    binary is NOT required. This lets the test logic be RED for the right reason
    (module `ocr_mcp.ocr` doesn't exist) rather than for a missing binary.
    T015 also mocks pytesseract so filters can be exercised in isolation.

Import guard:
    The tests import `ocr_mcp.ocr` directly; since that module doesn't exist yet
    the import will raise `ModuleNotFoundError`, which pytest collects as an ERROR
    (not a PASS) — that is valid RED evidence.

Covers:
    T010 [P] [DbC] — AC2: extract_exam_lines returns list with known exam substrings
                          from a synthesized PIL image.
    T011 [P] [DbC] — AC4: extract_exam_lines returns [] for a noise/blank image.
    T015 [P] [DbC] — AC2, AC4 (filter): _filter_lines (or public behaviour of
                          extract_exam_lines) excludes header prefixes and whitespace.
"""

from __future__ import annotations

import asyncio
import base64
import io
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# T010: synthesized image with known exam names returns non-empty list
# ---------------------------------------------------------------------------


class TestExtractReturnsLinesFromSynthesizedImage:
    """T010 [DbC] [AC2]: extract_exam_lines returns lines matching known exam names."""

    @pytest.mark.asyncio
    async def test_extract_returns_lines_from_synthesized_image(self) -> None:
        """T010: PIL-synthesized image with exam names → list contains substrings.

        Pre:  image_bytes is a valid PNG rendered with PIL.ImageDraw.
        Post: at least one returned line contains substring "Hemograma".
        DbC:  ocr.extract_exam_lines Post — len ≤ 64; each item 3..120 chars.
        AC2.
        """
        from ocr_mcp import ocr  # noqa: PLC0415 — module doesn't exist → RED

        # Synthesize a 400x100 white image with exam names drawn in black.
        # Import Pillow here so the test body is clear; Pillow is already a dev-dep.
        from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

        img = Image.new("RGB", (400, 100), "white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        exam_text = "Hemograma Completo\nGlicemia de Jejum\nTSH"
        draw.text((10, 10), exam_text, fill="black", font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Mock pytesseract so no real binary needed; return the known text.
        raw_ocr_output = "Hemograma Completo\nGlicemia de Jejum\nTSH\n"
        with patch("pytesseract.image_to_string", return_value=raw_ocr_output):
            result = await ocr.extract_exam_lines(png_bytes, lang="por", timeout_s=5.0)

        assert isinstance(result, list), "result must be a list"
        assert len(result) > 0, "must return at least one line"

        # Fuzzy check: each expected name must appear as substring in some line.
        expected_names = ["Hemograma", "Glicemia", "TSH"]
        all_returned = " ".join(result)
        for name in expected_names:
            assert name in all_returned, (
                f"Expected substring '{name}' not found in any returned line: {result}"
            )

        # DbC post-conditions
        assert all(3 <= len(line) <= 120 for line in result), (
            "All lines must be between 3 and 120 chars"
        )
        assert len(result) <= 64, "Result must have at most 64 lines"


# ---------------------------------------------------------------------------
# T011: noise/blank image → empty list
# ---------------------------------------------------------------------------


class TestExtractReturnsEmptyWhenImageIsNoise:
    """T011 [DbC] [AC4]: noise/blank image returns []."""

    @pytest.mark.asyncio
    async def test_extract_returns_empty_when_image_is_noise(self) -> None:
        """T011: blank white image with no text → extract_exam_lines returns [].

        Pre:  image_bytes is a valid PNG with no recognisable text.
        Post: returns empty list — no fallback, no silent failure.
        DbC:  ocr.extract_exam_lines Post — [] is valid output.
        AC4.
        """
        from ocr_mcp import ocr  # noqa: PLC0415 — module doesn't exist → RED

        from PIL import Image  # noqa: PLC0415

        img = Image.new("RGB", (200, 100), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Tesseract on a blank image returns empty string / very short fragments.
        with patch("pytesseract.image_to_string", return_value=""):
            result = await ocr.extract_exam_lines(png_bytes, lang="por", timeout_s=5.0)

        assert result == [], f"Expected [], got {result}"


# ---------------------------------------------------------------------------
# T015: filter heuristics — headers dropped, whitespace dropped
# ---------------------------------------------------------------------------


class TestFilterHeuristics:
    """T015 [P] [DbC] — AC2, AC4 (filter): header and whitespace filtering.

    Exercises the filtering behaviour of extract_exam_lines (or the internal
    _filter_lines helper if it is made public). Input is provided via a mocked
    pytesseract.image_to_string so the real binary is never invoked.

    The expected output for input:
        "Paciente: João\\nHemograma Completo\\n  \\nCPF: 111\\nECG"
    is:
        ["Hemograma Completo", "ECG"]

    "ECG" has 3 chars — exempt as uppercase medical acronym.
    "Paciente:" and "CPF:" are header prefixes — must be dropped.
    "  " (whitespace only) — must be dropped.
    AC2, AC4.
    """

    @pytest.mark.asyncio
    async def test_filter_heuristics(self) -> None:
        """T015: header prefixes and blank lines are excluded; acronyms kept.

        Pre:  pytesseract.image_to_string is mocked to return known multi-line text.
        Post: headers (Paciente:, CPF:) and whitespace lines absent from result;
              "Hemograma Completo" and "ECG" (uppercase acronym) present.
        """
        from ocr_mcp import ocr  # noqa: PLC0415 — module doesn't exist → RED

        raw_text = "Paciente: João\nHemograma Completo\n  \nCPF: 111\nECG"

        # Provide minimal valid PNG bytes (1×1 white pixel) as image input.
        from PIL import Image  # noqa: PLC0415

        img = Image.new("RGB", (10, 10), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        with patch("pytesseract.image_to_string", return_value=raw_text):
            result = await ocr.extract_exam_lines(png_bytes, lang="por", timeout_s=5.0)

        assert "Hemograma Completo" in result, (
            f"'Hemograma Completo' must be in result; got {result}"
        )
        assert "ECG" in result, f"'ECG' (uppercase acronym) must be in result; got {result}"

        # Header lines must be absent
        for item in result:
            assert not item.lower().startswith("paciente:"), (
                f"Header 'Paciente:' must be filtered out; found '{item}'"
            )
            assert not item.lower().startswith("cpf:"), (
                f"Header 'CPF:' must be filtered out; found '{item}'"
            )

        # Whitespace-only lines absent
        for item in result:
            assert item.strip() != "", "Whitespace-only lines must be filtered"


# ---------------------------------------------------------------------------
# Real-world E2E noise cases observed 2026-04-20 with sample_medical_order.png
# ---------------------------------------------------------------------------


class TestFilterRealWorldNoise:
    """Regression: heuristics must drop document-header noise observed in E2E.

    Real Tesseract output from sample_medical_order.png 2026-04-20:
        PEDIDOMEDICO            -> header (no colon, merged by OCR)
        CPF ITIAda 7775         -> field label (no colon, garbage value)
        Exames Solicitados.     -> section title (period, no colon)
        1 Hemegrama Completo    -> exam line WITH OCR typo (keep)
        2 Glicemiado Jejum      -> exam line WITH OCR merge (keep)
        a Colesterol Total      -> exam line WITH bad digit OCR (keep)
        atu                     -> 3-char lowercase fragment (drop)
        <LOCATION>              -> PII-masked token (keep — server layer)
    """

    @pytest.mark.asyncio
    async def test_filter_drops_real_world_document_headers(self) -> None:
        from ocr_mcp import ocr  # noqa: PLC0415

        from PIL import Image  # noqa: PLC0415

        img = Image.new("RGB", (10, 10), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        raw_text = (
            "PEDIDOMEDICO\n"
            "CPF ITIAda 7775\n"
            "Exames Solicitados.\n"
            "1 Hemegrama Completo\n"
            "2 Glicemiado Jejum\n"
            "a Colesterol Total\n"
            "atu\n"
        )

        with patch("pytesseract.image_to_string", return_value=raw_text):
            result = await ocr.extract_exam_lines(png_bytes, lang="por", timeout_s=5.0)

        # Document-header noise must be filtered out
        joined = " | ".join(result).lower()
        assert "pedidomedico" not in joined, f"'PEDIDOMEDICO' header leaked: {result}"
        assert "cpf " not in joined, f"'CPF ...' field label leaked: {result}"
        assert "exames solicitados" not in joined, (
            f"'Exames Solicitados' section title leaked: {result}"
        )
        assert "atu" not in result, f"'atu' 3-char fragment leaked: {result}"

        # Genuine exam lines (with OCR typos) must survive — RAG handles typos
        assert any("Hemegrama" in line or "Hemograma" in line for line in result), (
            f"exam line with 'Hemegrama/Hemograma' missing: {result}"
        )
        assert any("Glicemia" in line for line in result), (
            f"exam line with 'Glicemia' missing: {result}"
        )
        assert any("Colesterol" in line for line in result), (
            f"exam line with 'Colesterol' missing: {result}"
        )

    @pytest.mark.asyncio
    async def test_filter_keeps_short_medical_acronyms(self) -> None:
        """Short uppercase acronyms (TSH, HDL, PSA) are legit exam names and must survive.

        Bumping the minimum length unconditionally would kill them; the filter
        exempts uppercase acronyms.
        """
        from ocr_mcp import ocr  # noqa: PLC0415

        from PIL import Image  # noqa: PLC0415

        img = Image.new("RGB", (10, 10), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        raw_text = "TSH\nHDL\nPSA\nT3\natu\nvxy\n"

        with patch("pytesseract.image_to_string", return_value=raw_text):
            result = await ocr.extract_exam_lines(png_bytes, lang="por", timeout_s=5.0)

        for acronym in ("TSH", "HDL", "PSA", "T3"):
            assert acronym in result, f"Acronym '{acronym}' must survive: {result}"
        assert "atu" not in result, "lowercase noise 'atu' must drop"
        assert "vxy" not in result, "lowercase noise 'vxy' must drop"
