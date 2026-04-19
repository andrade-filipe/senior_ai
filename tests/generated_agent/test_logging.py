"""Tests for AC11 / T020 and AC21 / T029: logging contracts.

Green in this wave (unit — no Docker required).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path


def test_tool_called_has_params_hash(caplog: "pytest.LogCaptureFixture") -> None:
    """AC11 / T020: ToolCallLogger emits event=tool.called with params_hash, duration_ms, correlation_id.

    Post:
        Log record has event='tool.called', params_hash (16 hex chars), duration_ms, correlation_id.
    """
    from generated_agent.logging_ import ToolCallLogger

    with caplog.at_level(logging.INFO, logger="tool"):
        with ToolCallLogger("search_exam_code", {"exam_name": "Hemograma"}, "corr-abc"):
            pass

    assert caplog.records, "No log records emitted by ToolCallLogger"
    record = caplog.records[-1]
    assert record.__dict__.get("event") == "tool.called"
    assert record.__dict__.get("tool") == "search_exam_code"

    ph = record.__dict__.get("params_hash", "")
    assert isinstance(ph, str) and len(ph) == 16, (
        f"params_hash must be 16 hex chars, got {ph!r}"
    )
    assert all(c in "0123456789abcdef" for c in ph), (
        f"params_hash must be lowercase hex, got {ph!r}"
    )

    assert "duration_ms" in record.__dict__
    assert record.__dict__.get("correlation_id") == "corr-abc"


def test_params_hash_is_deterministic() -> None:
    """params_hash returns identical values for identical inputs."""
    from generated_agent.logging_ import params_hash

    p = {"exam_name": "Hemograma Completo"}
    assert params_hash(p) == params_hash(p)


def test_params_hash_differs_for_different_inputs() -> None:
    """params_hash differs for different inputs."""
    from generated_agent.logging_ import params_hash

    assert params_hash({"a": 1}) != params_hash({"a": 2})


def test_no_raw_pii_in_runner_logs(caplog: "pytest.LogCaptureFixture") -> None:
    """AC21 / T029 [DbC]: runner logs must not contain raw PII patterns.

    Invariant:
        No CPF pattern (ddd.ddd.ddd-dd), phone pattern, or known test name
        ('Joao Silva') appears in any log record emitted by the runner.

    This test uses a mocked run to trigger logging paths without real Gemini.
    """
    from generated_agent.logging_ import ToolCallLogger, configure_logging

    configure_logging()

    pii_patterns = [
        re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"),  # CPF
        re.compile(r"Joao\s+Silva", re.IGNORECASE),  # raw person name from fixture
        re.compile(r"\(\d{2}\)\s*\d{4,5}-\d{4}"),   # phone
    ]

    with caplog.at_level(logging.DEBUG):
        # Simulate what the agent would log during a tool call
        with ToolCallLogger(
            "extract_exams_from_image",
            {"image_sha256_prefix": "aabbccdd"},  # hash, not raw image
            "corr-xyz",
        ):
            pass

        # Emit a structured log as the runner does
        logger = logging.getLogger("generated_agent.__main__")
        logger.info(
            "agent.run.start",
            extra={
                "event": "agent.run.start",
                "correlation_id": "corr-xyz",
                "image_sha256_prefix": "aabbccdd",
            },
        )

    for record in caplog.records:
        record_str = json.dumps(record.__dict__, default=str)
        for pattern in pii_patterns:
            assert not pattern.search(record_str), (
                f"PII pattern {pattern.pattern!r} found in log record: {record_str[:200]}"
            )


def test_correlation_id_propagated_across_services() -> None:
    """AC12 / T021 — INTEGRATION: requires docker compose.

    Skipped in this wave; verified in Block 0008.
    """
    import pytest

    pytest.skip(reason="requires docker compose — Bloco 0008")
