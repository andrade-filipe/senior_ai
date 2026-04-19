"""Tests for OCR MCP guardrails — AC15, AC16, AC17 (T031, T032, T033).

Covers:
    T031 [DbC] [AC15]: image_base64 decoded > 5 MB → ToolError(E_OCR_IMAGE_TOO_LARGE)
    T032 [DbC] [AC16]: invalid base64 → ToolError(E_OCR_INVALID_INPUT)
    T033 [DbC] [AC17]: OCR timeout → ToolError(E_OCR_TIMEOUT)
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from ocr_mcp.server import extract_exams_from_image


class TestImageTooLargeRejected:
    """T031 [DbC] [AC15]: decoded bytes > 5 MB → E_OCR_IMAGE_TOO_LARGE."""

    @pytest.mark.asyncio
    async def test_image_too_large_rejected(self, oversized_base64: str) -> None:
        """T031: 6 MB image raises ToolError with E_OCR_IMAGE_TOO_LARGE."""
        with pytest.raises(ToolError) as exc_info:
            await extract_exams_from_image(oversized_base64)

        assert "E_OCR_IMAGE_TOO_LARGE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sha256_never_called_on_too_large(self, oversized_base64: str) -> None:
        """T031 [DbC]: sha256 is NOT computed when image exceeds cap."""
        with patch("ocr_mcp.fixtures.lookup") as mock_lookup:
            with pytest.raises(ToolError):
                await extract_exams_from_image(oversized_base64)
            # lookup (which calls sha256) must not have been called
            mock_lookup.assert_not_called()

    @pytest.mark.asyncio
    async def test_exactly_5mb_is_accepted(self) -> None:
        """T031: exactly 5 MB decoded is accepted (boundary)."""
        exactly_5mb = base64.b64encode(b"\x00" * (5 * 1024 * 1024)).decode()
        with patch("ocr_mcp.server._do_ocr", new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = []
            # Should not raise — 5 MB is exactly at cap, not above
            result = await extract_exams_from_image(exactly_5mb)
            assert result == []


class TestInvalidBase64Rejected:
    """T032 [DbC] [AC16]: invalid base64 → E_OCR_INVALID_INPUT."""

    @pytest.mark.asyncio
    async def test_invalid_base64_rejected(self) -> None:
        """T032: non-base64 string raises ToolError with E_OCR_INVALID_INPUT."""
        with pytest.raises(ToolError) as exc_info:
            await extract_exams_from_image("não é base64!")

        assert "E_OCR_INVALID_INPUT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_string_rejected(self) -> None:
        """T032: empty string raises ToolError with E_OCR_INVALID_INPUT."""
        with pytest.raises(ToolError) as exc_info:
            await extract_exams_from_image("")

        assert "E_OCR_INVALID_INPUT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_whitespace_only_rejected(self) -> None:
        """T032: whitespace-only string raises ToolError with E_OCR_INVALID_INPUT."""
        with pytest.raises(ToolError) as exc_info:
            await extract_exams_from_image("   ")

        assert "E_OCR_INVALID_INPUT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_partial_base64_rejected(self) -> None:
        """T032: string that looks like base64 but has invalid chars is rejected."""
        with pytest.raises(ToolError) as exc_info:
            await extract_exams_from_image("SGVsbG8!@#World")  # invalid chars

        assert "E_OCR_INVALID_INPUT" in str(exc_info.value)


class TestOcrTimeout:
    """T033 [DbC] [AC17]: OCR exceeds 5 s → E_OCR_TIMEOUT."""

    @pytest.mark.asyncio
    async def test_ocr_timeout(self, valid_small_base64: str) -> None:
        """T033: monkey-patch _do_ocr with > 5 s sleep → E_OCR_TIMEOUT."""
        async def slow_ocr(_: str) -> list[str]:
            await asyncio.sleep(10)
            return []

        with patch("ocr_mcp.server._do_ocr", new=slow_ocr):
            with patch("ocr_mcp.server._OCR_TIMEOUT_S", 0.05):  # speed up for tests
                with pytest.raises(ToolError) as exc_info:
                    await extract_exams_from_image(valid_small_base64)

        assert "E_OCR_TIMEOUT" in str(exc_info.value)
