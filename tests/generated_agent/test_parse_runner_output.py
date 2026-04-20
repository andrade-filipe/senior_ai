"""RED tests for Camada B — _parse_runner_output + _strip_json_fence.

Spec 0009 tasks T018–T019. Exercises the parser's end-to-end behavior:
- fenced canonical JSON → RunnerSuccess (fence stripper path, AC3)
- RunnerError envelope → SystemExit(4) with envelope on stderr (AC4)
- Legacy malformed output → SystemExit(3) (AC6, preserved)
"""

from __future__ import annotations

import json

import pytest


CANONICAL_SUCCESS_JSON = json.dumps(
    {
        "status": "success",
        "exams": [
            {"name": "Hemograma Completo", "code": "HEMO", "score": 0.92, "inconclusive": False},
        ],
        "appointment_id": "appt-42",
        "scheduled_for": "2026-04-21T09:00:00-03:00",
    }
)

CANONICAL_ERROR_JSON = json.dumps(
    {
        "status": "error",
        "error": {
            "code": "E_OCR_UNKNOWN_IMAGE",
            "message": "OCR nao reconheceu a imagem.",
            "hint": "Registre a fixture.",
        },
    }
)


class TestStripJsonFence:
    """Unit-level — the pure function that unblocks the gemini-2.5-pro E2E."""

    def test_strips_json_fence(self) -> None:
        from generated_agent.__main__ import _strip_json_fence  # noqa: PLC0415

        raw = f"```json\n{CANONICAL_SUCCESS_JSON}\n```"
        assert _strip_json_fence(raw).strip().startswith("{")
        assert "```" not in _strip_json_fence(raw)

    def test_strips_plain_fence(self) -> None:
        from generated_agent.__main__ import _strip_json_fence  # noqa: PLC0415

        raw = f"```\n{CANONICAL_SUCCESS_JSON}\n```"
        cleaned = _strip_json_fence(raw)
        assert "```" not in cleaned
        assert cleaned.strip().startswith("{")

    def test_preserves_unfenced(self) -> None:
        from generated_agent.__main__ import _strip_json_fence  # noqa: PLC0415

        assert _strip_json_fence(CANONICAL_SUCCESS_JSON).strip() == CANONICAL_SUCCESS_JSON.strip()

    def test_strips_leading_prose(self) -> None:
        from generated_agent.__main__ import _strip_json_fence  # noqa: PLC0415

        raw = f"Claro! Aqui esta o JSON solicitado:\n\n```json\n{CANONICAL_SUCCESS_JSON}\n```"
        cleaned = _strip_json_fence(raw)
        assert cleaned.strip().startswith("{")
        assert cleaned.strip().endswith("}")


class _FakePart:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.parts = [_FakePart(text)]


class _FakeEvent:
    def __init__(self, text: str) -> None:
        self.content = _FakeContent(text)


class TestParseRunnerOutput:
    """T018 [DbC] + T019 [DbC]."""

    def test_success_round_trip_returns_runner_success(self) -> None:
        from generated_agent.__main__ import RunnerSuccess, _parse_runner_output  # noqa: PLC0415

        event = _FakeEvent(f"```json\n{CANONICAL_SUCCESS_JSON}\n```")
        result = _parse_runner_output(event, correlation_id="test-cid")
        assert isinstance(result, RunnerSuccess)
        assert result.appointment_id == "appt-42"

    def test_error_envelope_exits_with_code_4(self, capsys: pytest.CaptureFixture[str]) -> None:
        from generated_agent.__main__ import _parse_runner_output  # noqa: PLC0415

        event = _FakeEvent(CANONICAL_ERROR_JSON)
        with pytest.raises(SystemExit) as exc_info:
            _parse_runner_output(event, correlation_id="test-cid")
        assert exc_info.value.code == 4

        captured = capsys.readouterr()
        envelope = json.loads(captured.err.strip().splitlines()[-1])
        assert envelope["error"]["code"] == "E_AGENT_OUTPUT_REPORTED_ERROR"
        assert envelope["correlation_id"] == "test-cid"

    def test_malformed_output_exits_with_code_3(self, capsys: pytest.CaptureFixture[str]) -> None:
        from generated_agent.__main__ import _parse_runner_output  # noqa: PLC0415

        event = _FakeEvent("not json at all, just prose")
        with pytest.raises(SystemExit) as exc_info:
            _parse_runner_output(event, correlation_id="test-cid")
        assert exc_info.value.code == 3

        captured = capsys.readouterr()
        envelope = json.loads(captured.err.strip().splitlines()[-1])
        assert envelope["error"]["code"] == "E_AGENT_OUTPUT_INVALID"
