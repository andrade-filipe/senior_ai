"""Test AC20 / T031: instruction byte cap enforcement.

Green in this wave (unit — no Docker required).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_instruction_under_4kb_cap(spec_example_path: str) -> None:
    """AC20 / T031 [DbC]: spec.example.json instruction is <= 4096 bytes UTF-8.

    Invariant:
        len(instruction.encode('utf-8')) <= 4096  (ADR-0008 / AC20)
    """
    from transpiler.schema import load_spec

    spec = load_spec(spec_example_path)
    byte_len = len(spec.instruction.encode("utf-8"))
    assert byte_len <= 4096, (
        f"instruction exceeds 4096 bytes: {byte_len} bytes. "
        "Reduce the instruction text to respect the cap (ADR-0008)."
    )


def test_instruction_over_4kb_rejected() -> None:
    """AC20 / T031 [DbC]: spec with instruction > 4096 bytes is rejected by load_spec.

    Post:
        load_spec raises TranspilerError(code='E_TRANSPILER_SCHEMA') for over-cap instruction.
    """
    from transpiler.errors import TranspilerError
    from transpiler.schema import load_spec

    long_instruction = "A" * 4097  # 4097 ASCII bytes > 4096 limit
    spec_dict = {
        "name": "test-agent",
        "description": "test",
        "model": "gemini-2.5-flash",
        "instruction": long_instruction,
        "mcp_servers": [{"name": "ocr", "url": "http://localhost:8001/sse"}],
        "http_tools": [],
    }
    with pytest.raises(TranspilerError) as exc_info:
        load_spec(spec_dict)
    assert exc_info.value.code == "E_TRANSPILER_SCHEMA"
    assert "4096" in exc_info.value.message or "instruction" in exc_info.value.message.lower()


def test_instruction_exactly_4096_bytes_accepted() -> None:
    """Boundary: instruction of exactly 4096 ASCII bytes must be accepted."""
    from transpiler.schema import load_spec

    exact_instruction = "B" * 4096
    spec_dict = {
        "name": "test-agent",
        "description": "test",
        "model": "gemini-2.5-flash",
        "instruction": exact_instruction,
        "mcp_servers": [{"name": "ocr", "url": "http://localhost:8001/sse"}],
        "http_tools": [],
    }
    spec = load_spec(spec_dict)
    assert len(spec.instruction.encode("utf-8")) == 4096
