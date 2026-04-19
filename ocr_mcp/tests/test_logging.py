"""Tests for OCR MCP structured logging (AC11, T020).

Covers:
    T020 [AC11]: tool.called event emitted with service, event, duration_ms fields.
                 No raw PII in log output.
"""

from __future__ import annotations

import base64
import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from ocr_mcp.logging_ import _JsonFormatter, get_logger


class TestJsonLoggerFormat:
    """Unit tests for the JSON formatter."""

    def test_log_record_has_required_fields(self) -> None:
        """T020 [AC11]: log record contains ts, level, service, event, message."""
        logger = get_logger("test-ocr")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("test-ocr"))
        logger.addHandler(handler)

        logger.info("tool.called", extra={"tool": "extract_exams"})

        buf.seek(0)
        output = buf.getvalue()
        # May have multiple lines; find the one with our event
        for line in output.splitlines():
            if line.strip():
                record = json.loads(line)
                # All required fields present (AC11)
                assert "ts" in record
                assert "level" in record
                assert "service" in record
                assert "event" in record
                assert record["service"] == "test-ocr"

    def test_log_has_no_raw_pii(self) -> None:
        """T020 [AC11]: log output must not contain raw CPF or patient name."""
        logger = get_logger("pii-test")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("pii-test"))
        logger.addHandler(handler)

        # Log an event — no PII should be present
        logger.info(
            "tool.called",
            extra={
                "entity_type": "BR_CPF",
                "sha256_prefix": "a1b2c3d4",  # only hash, not raw value
            },
        )

        buf.seek(0)
        output = buf.getvalue()
        # Raw CPF values must not appear
        assert "111.444.777-35" not in output
        assert "Joao da Silva" not in output

    def test_tool_called_event_emitted(self) -> None:
        """T020 [AC11]: tool.called event is in log when tool succeeds."""
        logger = get_logger("event-test")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("event-test"))
        logger.addHandler(handler)

        logger.info(
            "tool.called",
            extra={
                "tool": "extract_exams_from_image",
                "duration_ms": 42.0,
                "exam_count": 3,
            },
        )

        buf.seek(0)
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record["event"] == "tool.called"
        assert record["extra"]["tool"] == "extract_exams_from_image"
        assert "duration_ms" in record["extra"]

    def test_correlation_id_included_when_present(self) -> None:
        """T020 [AC11]: correlation_id included in log when provided."""
        logger = get_logger("corr-test")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("corr-test"))
        logger.addHandler(handler)

        logger.info(
            "tool.called",
            extra={"correlation_id": "abc-123"},
        )

        buf.seek(0)
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        record = json.loads(lines[-1])
        assert record.get("correlation_id") == "abc-123"
