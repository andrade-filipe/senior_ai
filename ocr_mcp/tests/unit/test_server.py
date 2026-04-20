"""RED tests for ocr_mcp.server._do_ocr and extract_exams_from_image — T013, T014, T016, T017.

These tests MUST FAIL until:
    - fixtures.lookup() returns None on miss (T013, T014 depend on this contract).
    - server._do_ocr delegates to ocr.extract_exam_lines on None (T014).
    - PII masking is applied to real-OCR output (T016).
    - E_OCR_TIMEOUT fires when ocr.extract_exam_lines hangs (T017).

The current server._do_ocr calls `lookup(image_base64)` and never calls
`ocr.extract_exam_lines` — so T013 (fast-path), T014 (fallback), T016 (PII on OCR
output), and T017 (timeout on real OCR) all reflect intended behaviour that does
not yet exist.

Import strategy:
    - `from ocr_mcp import ocr` will raise ImportError since ocr.py doesn't
      exist yet. T013/T016/T017 monkeypatch it at the `ocr_mcp.server` level via
      the string path "ocr_mcp.server.ocr" — which will also fail since `server.py`
      doesn't import `ocr` yet. Both failures are valid RED evidence.

Covers:
    T013 [P] [DbC] — AC1: _do_ocr uses fixture fast-path; ocr.extract_exam_lines NOT called.
    T014 [P] [DbC] — AC2: _do_ocr falls back to real OCR when lookup returns None.
    T016 [P] [DbC] — AC3: pii_mask is applied to real-OCR output.
    T017 [P] [DbC] — AC6: E_OCR_TIMEOUT fired when ocr.extract_exam_lines hangs.
"""

from __future__ import annotations

import asyncio
import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from ocr_mcp import fixtures
from ocr_mcp.server import _do_ocr, extract_exams_from_image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_b64(content: bytes = b"dummy_image") -> str:
    """Encode bytes to base64 string."""
    return base64.b64encode(content).decode()


# ---------------------------------------------------------------------------
# T013: fast-path — fixture hit bypasses OCR entirely
# ---------------------------------------------------------------------------


class TestDoOcrUsesFixtureFastPath:
    """T013 [DbC] [AC1]: when fixtures.lookup returns a list, ocr is never invoked."""

    @pytest.mark.asyncio
    async def test_do_ocr_uses_fixture_fast_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T013: fixture hit → ocr.extract_exam_lines is NOT awaited.

        Pre:  fixtures.lookup is patched to return ["Canned"] (non-None).
        Post: ocr.extract_exam_lines is never called; return contains "Canned".
        DbC:  server._do_ocr Post — delegates to OCR only on miss.
        AC1.
        """
        # Patch fixtures.lookup to return a canned list (fast-path hit).
        monkeypatch.setattr(fixtures, "lookup", lambda b64: ["Canned"])

        # Patch ocr.extract_exam_lines as AsyncMock so we can assert not awaited.
        # NOTE: this patch path will fail until server.py imports `ocr` — RED.
        ocr_mock = AsyncMock(side_effect=AssertionError("OCR must not be called on fast-path"))
        with patch("ocr_mcp.server.ocr") as mock_ocr_module:
            mock_ocr_module.extract_exam_lines = ocr_mock

            # Also mock pii_mask to avoid Presidio spin-up.
            masked = MagicMock()
            masked.masked_text = "Canned"
            with patch("security.pii_mask", return_value=masked):
                result = await _do_ocr(_make_b64())

        # ocr.extract_exam_lines must never have been awaited.
        ocr_mock.assert_not_awaited()

        assert result == ["Canned"], f"Expected ['Canned'], got {result}"


# ---------------------------------------------------------------------------
# T014: fallback — fixture miss triggers real OCR
# ---------------------------------------------------------------------------


class TestDoOcrFallsBackToRealOcrOnMiss:
    """T014 [DbC] [AC2]: when fixtures.lookup returns None, ocr.extract_exam_lines is awaited."""

    @pytest.mark.asyncio
    async def test_do_ocr_falls_back_to_real_ocr_on_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T014: fixture miss → ocr.extract_exam_lines awaited with decoded bytes.

        Pre:  fixtures.lookup returns None.
              ocr.extract_exam_lines returns ["Hemograma"].
        Post: extract_exam_lines was awaited exactly once with the decoded bytes
              corresponding to the b64 input.
        DbC:  server._do_ocr Post — real OCR path taken on None.
        AC2.
        """
        random_bytes = os.urandom(32)
        b64_input = base64.b64encode(random_bytes).decode()

        # Fixture miss.
        monkeypatch.setattr(fixtures, "lookup", lambda b64: None)

        ocr_mock = AsyncMock(return_value=["Hemograma"])

        with patch("ocr_mcp.server.ocr") as mock_ocr_module:
            mock_ocr_module.extract_exam_lines = ocr_mock

            masked = MagicMock()
            masked.masked_text = "Hemograma"
            with patch("security.pii_mask", return_value=masked):
                result = await _do_ocr(b64_input)

        # ocr.extract_exam_lines must have been awaited exactly once.
        ocr_mock.assert_awaited_once()

        # The first positional argument must be the decoded bytes.
        call_args = ocr_mock.await_args
        assert call_args is not None, "ocr.extract_exam_lines was not awaited"
        actual_bytes = call_args.args[0]
        assert actual_bytes == random_bytes, (
            f"extract_exam_lines called with wrong bytes: {actual_bytes!r} "
            f"(expected {random_bytes!r})"
        )

        assert result == ["Hemograma"], f"Expected ['Hemograma'], got {result}"


# ---------------------------------------------------------------------------
# T016: PII masking applied to real-OCR output
# ---------------------------------------------------------------------------


class TestDoOcrPiiMasksRealOcrOutput:
    """T016 [DbC] [AC3]: PII mask applied to OCR-path output before return."""

    @pytest.mark.asyncio
    async def test_do_ocr_pii_masks_real_ocr_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T016: raw OCR line containing CPF is masked by Layer 1 (pii_mask).

        Pre:  fixtures.lookup returns None (OCR path).
              ocr.extract_exam_lines returns a line with a raw CPF.
        Post: returned list item does NOT contain the raw CPF "111.444.777-35"
              or the raw name "João Silva".
        DbC:  server._do_ocr Post (Layer 1 PII).
        AC3.
        """
        raw_ocr_line = "Paciente João Silva CPF 111.444.777-35 Hemograma"

        monkeypatch.setattr(fixtures, "lookup", lambda b64: None)

        ocr_mock = AsyncMock(return_value=[raw_ocr_line])

        pii_call_received: list[str] = []

        def mock_pii_mask(text: str, language: str = "pt") -> MagicMock:
            pii_call_received.append(text)
            result = MagicMock()
            # Simulate masking: replace PII tokens.
            result.masked_text = (
                text.replace("111.444.777-35", "<CPF>")
                    .replace("João Silva", "<PESSOA>")
            )
            return result

        with patch("ocr_mcp.server.ocr") as mock_ocr_module:
            mock_ocr_module.extract_exam_lines = ocr_mock

            with patch("security.pii_mask", side_effect=mock_pii_mask):
                result = await _do_ocr(_make_b64())

        # pii_mask must have been called with the raw OCR line.
        assert pii_call_received, "pii_mask must be called with OCR output"
        assert pii_call_received[0] == raw_ocr_line, (
            f"pii_mask called with wrong input: {pii_call_received[0]!r}"
        )

        # Raw PII must be absent from the returned value.
        assert len(result) == 1
        assert "111.444.777-35" not in result[0], (
            f"Raw CPF must not appear in output: {result[0]!r}"
        )
        assert "João Silva" not in result[0], (
            f"Raw name must not appear in output: {result[0]!r}"
        )


# ---------------------------------------------------------------------------
# T017: E_OCR_TIMEOUT when extract_exams_from_image hangs via real OCR
# ---------------------------------------------------------------------------


class TestExtractToolTimeoutWhenRealOcrHangs:
    """T017 [DbC] [AC6]: E_OCR_TIMEOUT fires when ocr.extract_exam_lines hangs.

    The timeout is controlled by OCR_TIMEOUT_SECONDS env var.
    The test sets it to 0.2 s and patches ocr.extract_exam_lines to sleep 10 s.
    The public tool extract_exams_from_image must raise ToolError E_OCR_TIMEOUT.
    AC6.
    """

    @pytest.mark.asyncio
    async def test_extract_tool_timeout_when_real_ocr_hangs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T017: OCR hangs 10 s; timeout=0.2 s → ToolError[E_OCR_TIMEOUT].

        Pre:  fixtures.lookup returns None (force OCR path).
              ocr.extract_exam_lines sleeps for 10 s (hangs).
              OCR_TIMEOUT_SECONDS is set to 0.2 via monkeypatch of server var.
        Post: ToolError raised with code E_OCR_TIMEOUT in message.
        DbC:  server.extract_exams_from_image Invariant — timeout hard 5 s.
        AC6.
        """
        # Force OCR path.
        monkeypatch.setattr(fixtures, "lookup", lambda b64: None)

        async def hanging_ocr(*args: object, **kwargs: object) -> list[str]:
            await asyncio.sleep(10)
            return []  # unreachable

        b64_input = _make_b64(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        with patch("ocr_mcp.server.ocr") as mock_ocr_module:
            mock_ocr_module.extract_exam_lines = hanging_ocr

            # Patch the timeout constant to 0.2 s to keep tests fast.
            with patch("ocr_mcp.server._OCR_TIMEOUT_S", 0.2):
                with pytest.raises(ToolError) as exc_info:
                    await extract_exams_from_image(b64_input)

        assert "E_OCR_TIMEOUT" in str(exc_info.value), (
            f"Expected E_OCR_TIMEOUT in ToolError message, got: {exc_info.value}"
        )
