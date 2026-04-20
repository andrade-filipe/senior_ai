"""Spec 0009 T013 — ocr.lookup.hash event is emitted on every tool call.

The log is the instrumentation that decides Q1 of spec 0009: if the digest
recorded here matches the on-disk fixture hash during an E2E run, then the
lookup miss has a cause other than Gemini re-encoding the payload. If it
diverges, we register the observed hash via fixtures.register_fixture.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

from ocr_mcp.logging_ import _JsonFormatter
from ocr_mcp.server import extract_exams_from_image, logger as server_logger


@pytest.mark.asyncio
async def test_lookup_emits_hash_log(sample_png_base64: str) -> None:
    """T013: extract_exams_from_image emits `ocr.lookup.hash` with the sha256
    of the decoded payload the tool actually received.

    _do_ocr is mocked — this test is about the instrumentation log, not the
    PII/lookup pipeline. Without the mock, cold-starting spaCy pt_core_news_lg
    inside pytest exceeds OCR_TIMEOUT_SECONDS (5s) on first run.
    """
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(_JsonFormatter("ocr-mcp"))
    server_logger.addHandler(handler)
    try:
        with patch("ocr_mcp.server._do_ocr", new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = []
            await extract_exams_from_image(sample_png_base64)
    finally:
        server_logger.removeHandler(handler)

    expected_digest = hashlib.sha256(
        base64.b64decode(sample_png_base64, validate=True)
    ).hexdigest()

    hash_events = [
        json.loads(line)
        for line in buf.getvalue().splitlines()
        if line.strip() and '"ocr.lookup.hash"' in line
    ]
    assert hash_events, "expected at least one ocr.lookup.hash log event"

    record = hash_events[-1]
    assert record["event"] == "ocr.lookup.hash"
    assert record["extra"]["sha256"] == expected_digest
    assert record["extra"]["sha256_prefix"] == expected_digest[:12]
    assert record["extra"]["payload_bytes"] > 0
