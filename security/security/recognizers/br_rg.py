"""Brazilian RG (Registro Geral) recognizer for Presidio.

Strategy: regex-only (no checksum validation — RG format and digit rules vary
by issuing state/UF, making a universal checksum impractical).

Score: fixed at 0.5 (lower than CPF/CNPJ due to higher ambiguity — short digit
sequences can appear in many non-PII contexts).

Accepted formats (most common in SP and other states):
    12.345.678-9    (SP format — two dots, one hyphen, digit or X/x as check)
    12.345.678-X
    123456789       (raw digits, no punctuation — 9 chars)

Reference: no federal standard; formats documented per UF by IIRGD.

Note: RG evasion via spaces is NOT covered by this recognizer (plan.md § Risks).

MINOR-6 — Ambiguity limitation:
    The pattern r'\\b\\d{1,2}\\.?\\d{3}\\.?\\d{3}-?[\\dXx]\\b' may produce false positives
    on date-like strings (e.g. '12.345.678-9' resembles a date in some locales) or
    other numeric sequences.  Context words (_RG_CONTEXT) boost confidence and
    help reduce FP in practice, but the recognizer cannot be made fully precise
    without a format prefix (e.g. mandatory 'RG' keyword) at the cost of lower recall.
    Accepted as a known limitation for MVP; score kept at 0.5 to reduce impact.
    If FP rate is unacceptable in production, add mandatory context via context_filter.
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# Primary pattern: formatted RG with optional punctuation.
# Covers SP format (XX.XXX.XXX-D) and adjacent formats.
# The check digit can be a digit or X/x (common in SP).
_RG_PATTERN_FORMATTED = r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]\b"

_RG_CONTEXT = [
    "rg",
    "registro geral",
    "identidade",
    "cédula de identidade",
    "carteira de identidade",
    "r.g",
    "doc",
]

_SCORE_BASE = 0.5


class BRRGRecognizer(PatternRecognizer):
    """Presidio PatternRecognizer for Brazilian RG numbers.

    Uses regex only — no checksum validation because RG formats differ per UF.
    Score is intentionally lower (0.5) to reflect higher ambiguity.

    Post:
        All regex matches receive score == 0.5 regardless of formatting.
    """

    def __init__(self) -> None:
        patterns = [
            Pattern(name="BR_RG", regex=_RG_PATTERN_FORMATTED, score=_SCORE_BASE),
        ]
        super().__init__(
            supported_entity="BR_RG",
            patterns=patterns,
            context=_RG_CONTEXT,
            supported_language="pt",
        )
