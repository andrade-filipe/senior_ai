"""Tests for BRCPFRecognizer — T014, T015 (ADR-0004 test-first).

AC5: Valid CPF detected with score >= 0.85.
AC6: Invalid-checksum CPF (000.000.000-00) NOT masked as CPF (score below threshold).

DbC (plan.md § Design by Contract):
    Post:  score == 0.85 when checksum is valid.
    Invariant: validation_callback runs on every regex match.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "cpf_text",
    [
        "CPF 111.444.777-35",
        "cpf: 111.444.777-35",
        "cadastro de pessoa física 111.444.777-35",
        "111.444.777-35",  # without context keyword
    ],
)
def test_valid_cpf_detected_score_above_threshold(cpf_text: str) -> None:
    """T014 [DbC] — AC5: valid CPF has score >= 0.85.

    A mathematically valid CPF must be detected by the recognizer with a score
    of at least 0.85 (regex + checksum validation combined).
    """
    from security.recognizers.br_cpf import BRCPFRecognizer

    recognizer = BRCPFRecognizer()
    results = recognizer.analyze(text=cpf_text, entities=["BR_CPF"])

    assert len(results) >= 1, f"No BR_CPF entity found in: {cpf_text!r}"
    best = max(results, key=lambda r: r.score)
    assert best.score >= 0.85, (
        f"Expected score >= 0.85 for valid CPF, got {best.score} in: {cpf_text!r}"
    )


def test_invalid_digit_cpf_not_masked(invalid_cpf: str) -> None:
    """T015 [DbC] — AC6: CPF with invalid checksum is NOT masked (recognizer level).

    000.000.000-00 matches the regex but fails pycpfcnpj checksum validation.
    Score must be below 0.85 (the masking threshold).
    """
    from security.recognizers.br_cpf import BRCPFRecognizer

    recognizer = BRCPFRecognizer()
    text = f"CPF {invalid_cpf}"
    results = recognizer.analyze(text=text, entities=["BR_CPF"])

    # If detected, score must be < 0.85 (will not be masked at the guard level)
    for result in results:
        assert result.score < 0.85, (
            f"Invalid-checksum CPF should NOT have score >= 0.85, "
            f"got {result.score} for {invalid_cpf!r}"
        )


@pytest.mark.requires_spacy
def test_invalid_cpf_not_masked_via_pii_mask(invalid_cpf: str) -> None:
    """MAJOR-4 fix — AC6 tested via public pii_mask API.

    Calling pii_mask with an invalid-checksum CPF must NOT replace the CPF
    with '<CPF>' in the masked_text, because the score stays below the masking
    threshold.  This confirms that the full pipeline (not just the recognizer)
    respects checksum validation.

    Validated: 000.000.000-00 is rejected by pycpfcnpj.cpf.validate().
    """
    from security import pii_mask

    text = f"CPF {invalid_cpf}"
    result = pii_mask(text, language="pt")

    # The raw invalid CPF value must remain in masked_text (not replaced by <CPF>)
    assert invalid_cpf in result.masked_text, (
        f"Invalid-checksum CPF {invalid_cpf!r} should NOT be masked by pii_mask; "
        f"masked_text={result.masked_text!r}"
    )


def test_cpf_without_punctuation_detected(valid_cpf: str) -> None:
    """A CPF written without punctuation (digits only) is detected."""
    from security.recognizers.br_cpf import BRCPFRecognizer

    digits_only = valid_cpf.replace(".", "").replace("-", "")
    text = f"CPF {digits_only}"
    recognizer = BRCPFRecognizer()
    results = recognizer.analyze(text=text, entities=["BR_CPF"])

    assert len(results) >= 1
    assert max(r.score for r in results) >= 0.85


def test_cpf_not_detected_in_irrelevant_number_sequence() -> None:
    """A random 11-digit sequence that fails checksum should not reach high score."""
    from security.recognizers.br_cpf import BRCPFRecognizer

    # 12345678901 — all ascending digits; extremely unlikely to pass checksum
    text = "código: 123.456.789-01"
    recognizer = BRCPFRecognizer()
    results = recognizer.analyze(text=text, entities=["BR_CPF"])

    for result in results:
        # May or may not detect, but if detected it must not have a high score
        # unless the digits happen to satisfy the CPF checksum (very rare)
        if result.score >= 0.85:
            # Verify the score is justified by a passing checksum
            import re

            raw = text[result.start : result.end]
            digits = re.sub(r"\D", "", raw)
            import pycpfcnpj.cpf as cpf_val

            assert cpf_val.validate(digits), (
                f"Score 0.85 assigned to CPF with invalid checksum: {raw!r}"
            )
