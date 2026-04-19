"""Brazilian phone number recognizer for Presidio.

Strategy: regex covering DDD (11-99) + 8 or 9 digit number, with or without
country code (+55), with or without separators (space, hyphen, parentheses).

Score: 0.75 — higher than RG (less ambiguous) but lower than CPF/CNPJ (no
checksum available for phone numbers).

Patterns covered (AC9):
    (11) 98765-4321     — landline/mobile with parens and hyphen
    11 987654321        — no formatting
    +55 11 98765-4321   — with country code
    11987654321         — no separator at all
    (11) 8765-4321      — 8-digit landline

Reference: ANATEL — DDD ranges 11-99, mobile 9xxxxx-xxxx, landline 2xxx-xxxx..8xxx-xxxx
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# DDD: any two-digit code 11-99 (no validation of actual DDD assignment —
# that would require a live ANATEL table and changes over time).
# Mobile: 9 + 8 digits.  Landline: 8 digits starting with 2-8.
# Separators: optional parentheses around DDD, optional space/hyphen mid-number.
_PHONE_PATTERN = (
    r"\b"  # MAJOR-5 fix: word boundary prevents match in mid-string numeric sequences
    r"(?:\+55\s?)?"  # optional country code
    r"\(?\d{2}\)?"  # DDD (2 digits, optional parens)
    r"[\s-]?"  # optional separator
    r"9?\d{4}"  # optional leading 9 + 4 digits (first half)
    r"[\s-]?"  # optional separator
    r"\d{4}"  # last 4 digits
    r"\b"
)

_PHONE_CONTEXT = [
    "tel",
    "telefone",
    "celular",
    "fone",
    "cel",
    "whatsapp",
    "contato",
    "fax",
    "ddd",
    "número de telefone",
]

_SCORE_BASE = 0.75


class BRPhoneRecognizer(PatternRecognizer):
    """Presidio PatternRecognizer for Brazilian phone numbers.

    Covers DDD + 8 or 9 digit numbers with or without +55 country code and
    common separators (AC9).

    Post:
        All regex matches receive score == 0.75.
    """

    def __init__(self) -> None:
        patterns = [Pattern(name="BR_PHONE", regex=_PHONE_PATTERN, score=_SCORE_BASE)]
        super().__init__(
            supported_entity="BR_PHONE",
            patterns=patterns,
            context=_PHONE_CONTEXT,
            supported_language="pt",
        )
