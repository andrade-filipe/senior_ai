"""RED tests for Camada C — validator-pass via google.genai direct.

Spec 0009 tasks T024–T029. The validator-pass is an opt-in safety net that
reformats malformed agent output against the RunnerResult schema using a
second Gemini call (no ADK, no tools). Feature flag default OFF.

Invariant: _run_validator_pass NEVER raises to the caller. Any failure
(timeout, HTTP, JSON invalid) returns None so _parse_runner_output falls
back to the original exit-3 behavior (AC7).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


_CANONICAL_ERROR_JSON = json.dumps(
    {
        "status": "error",
        "error": {"code": "E_OCR_UNKNOWN_IMAGE", "message": "fail", "hint": None},
    }
)


@pytest.fixture(autouse=True)
def _disable_validator_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests that rely on disabled default don't pick up host env."""
    monkeypatch.delenv("AGENT_VALIDATOR_PASS_ENABLED", raising=False)


class TestRunValidatorPass:
    """T024–T027 [DbC] — the pure function contract."""

    def test_returns_none_on_timeout(self) -> None:
        from generated_agent.validator import _run_validator_pass  # noqa: PLC0415

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("timed out")

        with patch("generated_agent.validator._build_client", return_value=mock_client):
            result = _run_validator_pass("some text", correlation_id="cid-1")

        assert result is None

    def test_returns_json_string_on_success(self) -> None:
        from generated_agent.validator import _run_validator_pass  # noqa: PLC0415

        mock_response = MagicMock()
        mock_response.text = _CANONICAL_ERROR_JSON
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("generated_agent.validator._build_client", return_value=mock_client):
            result = _run_validator_pass("agent drifted output", correlation_id="cid-2")

        assert result == _CANONICAL_ERROR_JSON

    def test_returns_none_on_generic_error(self) -> None:
        from generated_agent.validator import _run_validator_pass  # noqa: PLC0415

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("503")

        with patch("generated_agent.validator._build_client", return_value=mock_client):
            result = _run_validator_pass("x", correlation_id="cid-3")

        assert result is None

    def test_respects_max_input_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from generated_agent.validator import _run_validator_pass  # noqa: PLC0415

        monkeypatch.setenv("VALIDATOR_MAX_INPUT_BYTES", "32")
        mock_client = MagicMock()
        with patch("generated_agent.validator._build_client", return_value=mock_client):
            oversized = "A" * 1024
            result = _run_validator_pass(oversized, correlation_id="cid-4")

        assert result is None
        mock_client.models.generate_content.assert_not_called()


class TestParseRunnerOutputValidatorIntegration:
    """T028–T029 — wiring into _parse_runner_output."""

    def _event(self, text: str) -> object:
        class _FakePart:
            def __init__(self, t: str) -> None:
                self.text = t

        class _FakeContent:
            def __init__(self, t: str) -> None:
                self.parts = [_FakePart(t)]

        class _FakeEvent:
            def __init__(self, t: str) -> None:
                self.content = _FakeContent(t)

        return _FakeEvent(text)

    def test_validator_pass_applied_on_drift(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from generated_agent.__main__ import _parse_runner_output  # noqa: PLC0415

        monkeypatch.setenv("AGENT_VALIDATOR_PASS_ENABLED", "true")

        canonical_success = json.dumps(
            {
                "status": "success",
                "exams": [
                    {"name": "Hemograma", "code": "HEMO", "score": 0.9, "inconclusive": False},
                ],
                "appointment_id": "appt-1",
                "scheduled_for": "2027-01-02T09:00:00Z",
            }
        )

        drift = "Here is my answer: {wrong: shape, not: json}"
        with patch(
            "generated_agent.validator._run_validator_pass",
            return_value=canonical_success,
        ):
            result = _parse_runner_output(self._event(drift), correlation_id="cid-d")

        assert result.appointment_id == "appt-1"

    def test_validator_pass_disabled_by_default(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from generated_agent.__main__ import _parse_runner_output  # noqa: PLC0415

        drift = "Here is my answer: {wrong: shape, not: json}"
        with pytest.raises(SystemExit) as exc_info:
            _parse_runner_output(self._event(drift), correlation_id="cid-e")
        assert exc_info.value.code == 3
