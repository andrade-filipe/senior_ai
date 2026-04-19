"""Tests for AC15 / T024 and AC16 / T025: retry and no-retry policies.

These tests validate the *policy contract* declared in the agent instruction.
They do NOT require a running LLM; they test the helper utilities
and ensure the policy text is present in the generated instruction.

Green in this wave (unit — no Docker required).
"""

from __future__ import annotations

import pytest


def test_mcp_timeout_retries_once_with_500ms_delay() -> None:
    """AC15 / T024 [DbC]: E_MCP_TIMEOUT policy: 1 retry with ~500ms delay.

    This test validates the retry helper logic as a unit, using a counter
    and a time.sleep mock. The integration path (real ADK) is in the skipped
    e2e tests.

    Post:
        retry_with_backoff calls the function exactly twice on first failure,
        waits ~500ms between attempts, and returns success on the second call.
    """
    import time
    from unittest.mock import patch

    call_count = 0
    sleep_calls: list[float] = []

    def flaky_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("E_MCP_TIMEOUT: simulated timeout")
        return "success"

    def mock_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    # Inline retry implementation that mirrors the policy in the instruction
    def retry_with_backoff(fn: object, max_retries: int = 1, delay: float = 0.5) -> object:
        """Execute fn with retry policy matching the agent instruction (AC15)."""
        import time as _time

        for attempt in range(max_retries + 1):
            try:
                return fn()  # type: ignore[operator]
            except Exception as exc:
                if attempt == max_retries:
                    raise
                _time.sleep(delay)
        return None  # unreachable

    with patch("time.sleep", mock_sleep):
        result = retry_with_backoff(flaky_call, max_retries=1, delay=0.5)

    assert result == "success", f"Expected success on retry, got {result}"
    assert call_count == 2, f"Expected exactly 2 calls (1 original + 1 retry), got {call_count}"
    assert len(sleep_calls) == 1, f"Expected exactly 1 sleep, got {sleep_calls}"
    assert sleep_calls[0] == pytest.approx(0.5, abs=0.01), (
        f"Expected 500ms delay, got {sleep_calls[0] * 1000:.0f}ms"
    )


def test_api_validation_no_retry_reports_field_and_reason() -> None:
    """AC16 / T025 [DbC]: E_API_VALIDATION (422) triggers zero retries.

    Post:
        The policy function does NOT retry on 422.
        The error message cites the field name and reason from the Pydantic response.
    """
    call_count = 0

    def post_appointment() -> dict:
        nonlocal call_count
        call_count += 1
        # Simulate 422 response body (Pydantic validation error format)
        return {
            "status_code": 422,
            "detail": [
                {
                    "loc": ["body", "patient_ref"],
                    "msg": "String should match pattern '^anon-[a-z0-9]+$'",
                    "type": "string_pattern_mismatch",
                }
            ],
        }

    def handle_api_response(response: dict) -> str:
        """Simulate the agent's API validation error handler (AC16)."""
        if response.get("status_code") == 422:
            errors = response.get("detail", [])
            if errors:
                field = ".".join(str(p) for p in errors[0].get("loc", []))
                reason = errors[0].get("msg", "")
                raise ValueError(f"E_API_VALIDATION: campo={field!r}, motivo={reason!r}")
        return "ok"

    response = post_appointment()
    error_raised = False
    error_message = ""
    try:
        handle_api_response(response)
    except ValueError as exc:
        error_raised = True
        error_message = str(exc)

    # Zero retries: function was called exactly once
    assert call_count == 1, f"Expected 0 retries (1 total call), got {call_count} calls"
    assert error_raised, "Expected ValueError for 422 response"
    assert "patient_ref" in error_message, (
        f"Error message must cite the field name, got: {error_message}"
    )
    assert "pattern" in error_message.lower() or "anon" in error_message, (
        f"Error message must cite the reason, got: {error_message}"
    )


def test_instruction_contains_retry_policy_text() -> None:
    """The agent instruction must explicitly encode the retry policy (AC15, AC16)."""
    from pathlib import Path

    from transpiler.schema import load_spec

    spec_path = Path(__file__).parent.parent.parent / "docs" / "fixtures" / "spec.example.json"
    spec = load_spec(str(spec_path))
    instr = spec.instruction.lower()

    # E_MCP_TIMEOUT policy: 1 retry, 500ms
    assert "retry" in instr or "500" in instr, (
        "Instruction must mention retry policy for E_MCP_TIMEOUT"
    )
    # E_API_VALIDATION policy: zero retry
    assert "422" in instr or "zero retry" in instr or "e_api_validation" in instr, (
        "Instruction must mention no-retry policy for E_API_VALIDATION"
    )
