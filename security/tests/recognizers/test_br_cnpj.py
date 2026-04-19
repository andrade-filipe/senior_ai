"""Tests for BRCNPJRecognizer — T016.

AC7: Valid CNPJ detected with score >= 0.85.
Negative case: CNPJ with invalid checksum gets score < 0.85.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "cnpj_text",
    [
        "CNPJ 11.222.333/0001-81",
        "cnpj: 11.222.333/0001-81",
        "razão social XYZ, CNPJ 11.222.333/0001-81",
        "11.222.333/0001-81",
    ],
)
def test_valid_cnpj_detected(cnpj_text: str) -> None:
    """T016 — AC7: valid CNPJ detected with score >= 0.85."""
    from security.recognizers.br_cnpj import BRCNPJRecognizer

    recognizer = BRCNPJRecognizer()
    results = recognizer.analyze(text=cnpj_text, entities=["BR_CNPJ"])

    assert len(results) >= 1, f"No BR_CNPJ entity found in: {cnpj_text!r}"
    best = max(results, key=lambda r: r.score)
    assert best.score >= 0.85, (
        f"Expected score >= 0.85 for valid CNPJ, got {best.score} in: {cnpj_text!r}"
    )


def test_invalid_cnpj_low_score(invalid_cnpj: str) -> None:
    """Negative case: CNPJ with invalid checksum must NOT reach score >= 0.85."""
    from security.recognizers.br_cnpj import BRCNPJRecognizer

    recognizer = BRCNPJRecognizer()
    text = f"CNPJ {invalid_cnpj}"
    results = recognizer.analyze(text=text, entities=["BR_CNPJ"])

    for result in results:
        assert result.score < 0.85, (
            f"Invalid-checksum CNPJ should not score >= 0.85, "
            f"got {result.score} for {invalid_cnpj!r}"
        )


def test_cnpj_without_punctuation_detected(valid_cnpj: str) -> None:
    """CNPJ written as 14 raw digits (no formatting) is detected."""
    from security.recognizers.br_cnpj import BRCNPJRecognizer

    import re

    digits_only = re.sub(r"\D", "", valid_cnpj)
    text = f"empresa CNPJ {digits_only}"
    recognizer = BRCNPJRecognizer()
    results = recognizer.analyze(text=text, entities=["BR_CNPJ"])

    assert len(results) >= 1
    assert max(r.score for r in results) >= 0.85
