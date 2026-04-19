"""Tests for BRPhoneRecognizer — T018.

AC9: BR phone numbers with DDD are detected in various formats.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "phone_text",
    [
        "(11) 98765-4321",  # standard mobile
        "11 987654321",  # no formatting
        "+55 11 98765-4321",  # with country code
        "(11) 8765-4321",  # 8-digit landline
        "tel: (11) 98765-4321",
        "celular 11987654321",
    ],
)
def test_br_phone_patterns_detected(phone_text: str) -> None:
    """T018 — AC9: Brazilian phone numbers in various formats are detected."""
    from security.recognizers.br_phone import BRPhoneRecognizer

    recognizer = BRPhoneRecognizer()
    results = recognizer.analyze(text=phone_text, entities=["BR_PHONE"])

    assert len(results) >= 1, f"No BR_PHONE entity found in: {phone_text!r}"
    best = max(results, key=lambda r: r.score)
    assert best.score >= 0.5, (
        f"Expected score >= 0.5 for phone, got {best.score} in: {phone_text!r}"
    )


def test_plain_text_without_phone_not_detected() -> None:
    """Non-numeric text does not produce false phone detections."""
    from security.recognizers.br_phone import BRPhoneRecognizer

    recognizer = BRPhoneRecognizer()
    results = recognizer.analyze(text="hemograma completo glicemia jejum", entities=["BR_PHONE"])
    # Allow zero results; any false positives here would be a problem
    for result in results:
        # If something is detected, it must have a low score
        assert result.score < 0.75
