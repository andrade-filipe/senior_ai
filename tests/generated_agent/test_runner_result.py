"""RED tests for Camada B — RunnerSuccess | RunnerError discriminated union.

Spec 0009 tasks T014–T017. These tests exercise the schema itself, not the
parser. They must fail before T050 (GREEN) lands because the current
generated_agent.__main__ still exposes only the legacy `_RunnerOutput`
without the `status` discriminator.
"""

from __future__ import annotations

import pytest


class TestRunnerSuccess:
    """T014 [DbC] [AC3]."""

    def test_success_shape_parses(self) -> None:
        from generated_agent.__main__ import RunnerSuccess  # noqa: PLC0415

        payload = {
            "status": "success",
            "exams": [
                {"name": "Hemograma Completo", "code": "HEMO", "score": 0.92, "inconclusive": False},
            ],
            "appointment_id": "appt-42",
            "scheduled_for": "2026-04-21T09:00:00-03:00",
        }
        instance = RunnerSuccess.model_validate(payload)
        assert instance.status == "success"
        assert len(instance.exams) == 1
        assert instance.appointment_id == "appt-42"


class TestRunnerError:
    """T015 [DbC] [AC4]."""

    def test_error_shape_parses(self) -> None:
        from generated_agent.__main__ import RunnerError  # noqa: PLC0415

        payload = {
            "status": "error",
            "error": {
                "code": "E_OCR_UNKNOWN_IMAGE",
                "message": "OCR nao reconheceu a imagem.",
                "hint": "Registre a fixture.",
            },
        }
        instance = RunnerError.model_validate(payload)
        assert instance.status == "error"
        assert instance.error.code == "E_OCR_UNKNOWN_IMAGE"
        assert instance.error.hint == "Registre a fixture."


class TestDiscriminator:
    """T016 + T017 — discriminator enforcement."""

    def test_missing_status_rejected(self) -> None:
        import pydantic  # noqa: PLC0415

        from generated_agent.__main__ import RunnerResultAdapter  # noqa: PLC0415

        payload = {
            "exams": [],
            "appointment_id": "a",
            "scheduled_for": "2026-04-21T09:00:00-03:00",
        }
        with pytest.raises(pydantic.ValidationError):
            RunnerResultAdapter.validate_python(payload)

    def test_mixed_shape_rejected(self) -> None:
        import pydantic  # noqa: PLC0415

        from generated_agent.__main__ import RunnerResultAdapter  # noqa: PLC0415

        payload = {
            "status": "success",
            "error": {"code": "X", "message": "y"},
        }
        with pytest.raises(pydantic.ValidationError):
            RunnerResultAdapter.validate_python(payload)
