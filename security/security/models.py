"""Data models for the PII guard module.

MaskedResult is the return type of pii_mask().  EntityHit holds metadata about
each detected entity WITHOUT storing the raw value — only a sha256 prefix is
kept for audit purposes (AC2, ADR-0008 § no-PII-in-logs).
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field, field_validator, model_validator


class EntityHit(BaseModel):
    """Metadata for one detected PII entity.

    Invariant:
        The ``sha256_prefix`` field contains the first 8 hex characters of the
        SHA-256 digest of the raw matched value.  The raw value itself is never
        stored (ADR-0008 § no-PII-in-logs, AC2, AC18).

    Attributes:
        entity_type: Presidio entity label (e.g. 'BR_CPF', 'PERSON').
        start: Start offset (inclusive) of the match in the original text.
        end: End offset (exclusive) of the match in the original text.
        score: Confidence score in [0.0, 1.0] as reported by Presidio.
        sha256_prefix: First 8 hex characters of sha256(raw_value).
                       Used only for audit correlation — never exposes the raw value.
    """

    entity_type: str = Field(..., min_length=1)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    score: float = Field(..., ge=0.0, le=1.0)
    sha256_prefix: str = Field(..., min_length=8, max_length=8)

    @field_validator("sha256_prefix")
    @classmethod
    def must_be_hex(cls, v: str) -> str:
        """Validate that sha256_prefix contains exactly 8 lowercase hex chars."""
        if not all(c in "0123456789abcdef" for c in v):
            msg = "sha256_prefix must be 8 lowercase hex characters"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "EntityHit":
        """Validate that end > start (non-empty span)."""
        if self.end <= self.start:
            msg = f"end ({self.end}) must be greater than start ({self.start})"
            raise ValueError(msg)
        return self


class MaskedResult(BaseModel):
    """Return value of pii_mask().

    Invariant:
        ``entities`` contains only EntityHit objects — no raw PII values
        anywhere in the structure (AC2, AC18).

    Attributes:
        masked_text: Input text with PII replaced by entity-type placeholders
                     (e.g. '<CPF>', '<PERSON>').
        entities: List of detected entities with metadata only (no raw values).
    """

    masked_text: str
    entities: list[EntityHit] = Field(default_factory=list)


def sha256_prefix(value: str) -> str:
    """Return the first 8 hex characters of the SHA-256 digest of ``value``.

    This is the only function in the module permitted to receive a raw PII value.
    It is called once per detected entity during anonymization and the raw value
    is immediately discarded.

    Args:
        value: Raw string to hash.  Must not be logged or stored after this call.

    Returns:
        First 8 lowercase hex characters of sha256(value.encode('utf-8')).

    Post:
        Return length == 8 and all characters are in [0-9a-f].
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    result = digest[:8]
    assert len(result) == 8, "sha256_prefix invariant: always 8 chars"  # noqa: S101
    return result
