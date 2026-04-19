"""Tests for BRRGRecognizer — T017.

AC8: RG in standard format detected via regex (no checksum validation).
Negative case: non-RG digit sequences are not falsely classified.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "rg_text",
    [
        "RG 12.345.678-9",
        "rg: 12.345.678-9",
        "identidade 12.345.678-9",
        "cédula de identidade 12.345.678-X",
        "carteira de identidade 12.345.678-x",
    ],
)
def test_rg_pattern_detected(rg_text: str) -> None:
    """T017 — AC8: formatted RG is detected via regex."""
    from security.recognizers.br_rg import BRRGRecognizer

    recognizer = BRRGRecognizer()
    results = recognizer.analyze(text=rg_text, entities=["BR_RG"])

    assert len(results) >= 1, f"No BR_RG entity found in: {rg_text!r}"
    best = max(results, key=lambda r: r.score)
    assert best.score >= 0.4, (
        f"Expected score >= 0.4 for RG, got {best.score} in: {rg_text!r}"
    )


def test_short_number_does_not_match_rg() -> None:
    """A 5-digit code that does not fit RG format should not be detected."""
    from security.recognizers.br_rg import BRRGRecognizer

    recognizer = BRRGRecognizer()
    results = recognizer.analyze(text="código 12345", entities=["BR_RG"])

    # Any detection must have score < 0.85 (RG has no checksum, can be noisy)
    for result in results:
        assert result.score < 0.85


@pytest.mark.xfail(
    reason=(
        "Known evasion: RG with zero-width space (e.g. '12.345\u200b.678-9') "
        "evades the regex boundary match.  Not yet handled.  "
        "MINOR-4 — tracked as follow-up issue."
    ),
    strict=True,
)
def test_rg_with_zero_width_space_is_detected() -> None:
    """Known evasion — RG split by U+200B zero-width space is NOT detected.

    This is an acknowledged limitation documented in plan.md § Risks.
    The test is marked xfail(strict=True) so that if the recognizer is ever
    improved to handle this case, the suite will alert the developer to update
    the mark.
    """
    from security.recognizers.br_rg import BRRGRecognizer

    recognizer = BRRGRecognizer()
    # U+200B inserted between groups — evades \b-anchored regex
    evaded_rg = "12.345\u200b.678-9"
    results = recognizer.analyze(text=f"RG {evaded_rg}", entities=["BR_RG"])
    # This assertion will FAIL (xfail) because the evasion works
    assert len(results) >= 1, "Should detect RG with zero-width space (currently evades)"
