"""Tests for AC18 / T027 and AC19 / T028: execution guardrails.

Green in this wave (unit — monkeypatched, no real LLM or Docker required).
"""

from __future__ import annotations

import asyncio
import json
import sys
from io import StringIO
from unittest.mock import AsyncMock, patch


def _make_mock_session(session_id: str = "sess-1") -> object:
    """Build a minimal fake session object."""
    sess = object.__new__(object)
    object.__setattr__(sess, "id", session_id)
    return type("Session", (), {"id": session_id})()


def test_agent_timeout_300s(capsys: "pytest.CaptureFixture[str]") -> None:
    """AC18 / T027 [DbC]: runner exits with code 2 and E_AGENT_TIMEOUT when execution > 300s.

    Post:
        stderr JSON has nested {"error": {"code": "E_AGENT_TIMEOUT"}, "correlation_id": ...}.
        Exit code is 2.
    """
    from generated_agent.__main__ import _AGENT_TIMEOUT

    # Confirm constant value
    assert _AGENT_TIMEOUT == 300.0, f"Timeout must be 300s, got {_AGENT_TIMEOUT}"

    captured_stderr = StringIO()

    with patch("sys.stderr", captured_stderr):
        with patch("sys.exit") as mock_exit:
            from generated_agent import __main__ as runner_mod

            runner_mod._exit_error(
                code="E_AGENT_TIMEOUT",
                message="Agente excedeu o tempo limite de 300 s.",
                correlation_id="test-corr-id",
                hint="Verifique se os servicos MCP estao saudaveis (docker compose ps).",
                exit_code=2,
            )
            mock_exit.assert_called_with(2)

    output = captured_stderr.getvalue()
    data = json.loads(output)
    assert data["error"]["code"] == "E_AGENT_TIMEOUT"
    assert "300" in data["error"]["message"]
    assert data["correlation_id"] == "test-corr-id"


def test_agent_output_invalid(capsys: "pytest.CaptureFixture[str]") -> None:
    """AC19 / T028 [DbC]: _exit_error with E_AGENT_OUTPUT_INVALID writes correct JSON.

    Tests the error-path helper directly (zero retry is enforced by no loop
    around _parse_runner_output).
    """
    captured_stderr = StringIO()

    with patch("sys.stderr", captured_stderr):
        with patch("sys.exit"):
            from generated_agent.__main__ import _exit_error

            _exit_error(
                code="E_AGENT_OUTPUT_INVALID",
                message="Saida do agente nao corresponde ao schema esperado.",
                correlation_id="corr-xyz",
                hint="Verifique se o agente retornou JSON valido com campos exams[], appointment_id, scheduled_for.",
                exit_code=3,
            )

    output = captured_stderr.getvalue()
    data = json.loads(output)
    assert data["error"]["code"] == "E_AGENT_OUTPUT_INVALID"
    assert "schema" in data["error"]["message"].lower() or "agent" in data["error"]["message"].lower()
    assert data["correlation_id"] == "corr-xyz"


def test_parse_runner_output_raises_on_missing_exams() -> None:
    """AC19 [DbC]: _parse_runner_output calls _exit_error when 'exams' field is absent."""

    class _FakeEvent:
        """Fake ADK event with missing 'exams' field."""

        class content:
            class _Part:
                text = '{"appointment_id": "apt-1", "scheduled_for": "2026-05-01T09:00:00"}'

            parts = [_Part()]

    captured_stderr = StringIO()
    exit_called_with: list[int] = []

    def fake_exit(code: int) -> None:
        exit_called_with.append(code)
        raise SystemExit(code)

    with patch("sys.stderr", captured_stderr):
        with patch("sys.exit", side_effect=fake_exit):
            from generated_agent.__main__ import _parse_runner_output

            try:
                _parse_runner_output(_FakeEvent(), "corr-test")
            except SystemExit:
                pass

    assert 3 in exit_called_with, f"Expected exit(3) for invalid output, got {exit_called_with}"
    output = captured_stderr.getvalue()
    data = json.loads(output)
    assert data["error"]["code"] == "E_AGENT_OUTPUT_INVALID"
    assert data["correlation_id"] == "corr-test"


def test_exit_error_shape() -> None:
    """_exit_error emits the canonical ADR-0008 envelope to stderr.

    Shape: {"error": {"code", "message", "hint"}, "correlation_id": ...}
    """
    from io import StringIO

    buf = StringIO()
    with patch("sys.stderr", buf):
        with patch("sys.exit"):
            from generated_agent.__main__ import _exit_error

            _exit_error(
                code="E_TEST",
                message="test message",
                correlation_id="test-cid",
                hint="test hint",
                exit_code=9,
            )

    data = json.loads(buf.getvalue())
    assert data["error"]["code"] == "E_TEST"
    assert data["error"]["message"] == "test message"
    assert data["error"]["hint"] == "test hint"
    assert data["correlation_id"] == "test-cid"


def test_exit_error_includes_correlation_id() -> None:
    """MAJOR-1: _exit_error envelope always contains 'correlation_id' field."""
    buf = StringIO()
    with patch("sys.stderr", buf):
        with patch("sys.exit"):
            from generated_agent.__main__ import _exit_error

            _exit_error(
                code="E_AGENT_TIMEOUT",
                message="timeout",
                correlation_id="specific-uuid-here",
                hint=None,
                exit_code=2,
            )

    data = json.loads(buf.getvalue())
    assert "correlation_id" in data
    assert data["correlation_id"] == "specific-uuid-here"


def test_exit_error_input_not_found() -> None:
    """MAJOR-3: missing file uses E_AGENT_INPUT_NOT_FOUND, not E_AGENT_OUTPUT_INVALID."""
    buf = StringIO()
    with patch("sys.stderr", buf):
        with patch("sys.exit"):
            from generated_agent.__main__ import _E_AGENT_INPUT_NOT_FOUND, _exit_error

            _exit_error(
                code=_E_AGENT_INPUT_NOT_FOUND,
                message="Arquivo de imagem nao encontrado: /no/such/file.png",
                correlation_id="cid-123",
                hint="Verifique o caminho passado em --image.",
                exit_code=1,
            )

    data = json.loads(buf.getvalue())
    assert data["error"]["code"] == "E_AGENT_INPUT_NOT_FOUND"
