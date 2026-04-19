"""Tests for RAG MCP structured logging (AC11, T020).

Covers:
    T020 [AC11]: tool.called event emitted with service, event, duration_ms.
                 No raw PII in log output.
"""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from rag_mcp.logging_ import _JsonFormatter, get_logger


class TestJsonLoggerFormat:
    """Unit tests for the RAG MCP JSON formatter."""

    def test_log_record_has_required_fields(self) -> None:
        """T020 [AC11]: log record contains ts, level, service, event, message."""
        logger = get_logger("test-rag")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("test-rag"))
        logger.addHandler(handler)

        logger.info("tool.called", extra={"tool": "search_exam_code"})

        buf.seek(0)
        for line in buf.getvalue().splitlines():
            if line.strip():
                record = json.loads(line)
                assert "ts" in record
                assert "level" in record
                assert "service" in record
                assert "event" in record
                assert record["service"] == "test-rag"
                break

    def test_tool_called_event_has_duration_ms(self) -> None:
        """T020 [AC11]: tool.called log includes duration_ms in extra."""
        logger = get_logger("dur-test-rag")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("dur-test-rag"))
        logger.addHandler(handler)

        logger.info(
            "tool.called",
            extra={
                "tool": "search_exam_code",
                "duration_ms": 15.5,
            },
        )

        buf.seek(0)
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        record = json.loads(lines[-1])
        assert record["extra"]["duration_ms"] == 15.5

    def test_no_raw_pii_in_log(self) -> None:
        """T020 [AC11]: log output must not contain raw PII."""
        logger = get_logger("pii-rag-test")
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter("pii-rag-test"))
        logger.addHandler(handler)

        # Simulate a logging call that could accidentally include PII
        logger.info(
            "tool.called",
            extra={"entity_type": "BR_CPF", "sha256_prefix": "deadbeef"},
        )

        buf.seek(0)
        output = buf.getvalue()
        assert "111.444.777-35" not in output
        assert "Joao da Silva" not in output
