"""Tests for ocr_mcp.fixtures — deterministic OCR mock (AC2, AC3, T011, T012).

Covers:
    T011 [AC2]: Known hash → canned list (determinism R11)
    T012 [AC3]: Unknown hash → empty list without raising
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from ocr_mcp import fixtures as fix_module
from ocr_mcp.fixtures import FIXTURES, _SAMPLE_EXAMS, _ensure_fixture_registered, lookup


class TestKnownHashReturnsCannedList:
    """T011 [AC2]: same hash → same list (determinism)."""

    def test_known_hash_returns_canned_list(self, sample_png_base64: str, sample_png_sha256: str) -> None:
        """T011: lookup() returns canned list for known image hash."""
        # Ensure the fixture is registered (may have just been generated)
        _ensure_fixture_registered()

        result = lookup(sample_png_base64)

        assert result == list(_SAMPLE_EXAMS)

    def test_same_input_same_output(self, sample_png_base64: str) -> None:
        """T011: determinism — identical input produces identical output."""
        _ensure_fixture_registered()

        result1 = lookup(sample_png_base64)
        result2 = lookup(sample_png_base64)

        assert result1 == result2

    def test_result_is_a_copy(self) -> None:
        """T011: lookup returns a copy — mutation does not affect FIXTURES."""
        # Register a custom fixture
        dummy_bytes = b"dummy_image_content_for_copy_test_abc123" * 10
        dummy_b64 = base64.b64encode(dummy_bytes).decode()
        dummy_hash = hashlib.sha256(dummy_bytes).hexdigest()
        FIXTURES[dummy_hash] = ["Exame A", "Exame B"]

        result = lookup(dummy_b64)
        result.append("Exame C")  # mutate return value

        # Original FIXTURES entry is unchanged
        assert FIXTURES[dummy_hash] == ["Exame A", "Exame B"]

    def test_fixture_contains_expected_exam_names(self, sample_png_base64: str) -> None:
        """T011 [AC2]: fixture contains the expected medical exam names."""
        _ensure_fixture_registered()
        result = lookup(sample_png_base64)

        assert "Hemograma Completo" in result
        assert "Glicemia de Jejum" in result
        assert "Colesterol Total" in result


class TestUnknownHashReturnsNone:
    """T012 [AC3/AC10]: unknown hash → None (spec 0011 breaking change).

    NOTE: contract changed in spec 0011 (Onda C GREEN). lookup() now returns
    None on miss instead of [] — callers must delegate to real OCR on None.
    """

    def test_unknown_hash_returns_none_without_error(self) -> None:
        """T012: lookup() returns None for an image not in FIXTURES (AC10)."""
        # Create a base64 string that definitely won't be in FIXTURES
        unknown_bytes = b"this_is_definitely_not_a_fixture_image_xyz987" * 100
        unknown_b64 = base64.b64encode(unknown_bytes).decode()

        result = lookup(unknown_b64)

        assert result is None, (
            f"lookup() must return None on miss (AC10), but got: {result!r}"
        )

    def test_unknown_returns_none_not_list(self) -> None:
        """T012: miss returns None, not a list (new contract AC10)."""
        b64 = base64.b64encode(b"random_unknown_content_xyz_789").decode()
        result = lookup(b64)
        assert result is None, (
            f"Expected None on miss, got {result!r}"
        )

    def test_unknown_image_returns_none_not_error(self) -> None:
        """T012 [AC10]: unknown image should not raise any exception — returns None."""
        b64 = base64.b64encode(b"some_completely_different_content_abc").decode()
        # Must not raise
        result = lookup(b64)
        assert result is None, (
            f"Expected None on miss, got {result!r}"
        )
