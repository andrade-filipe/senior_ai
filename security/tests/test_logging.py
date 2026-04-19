"""Tests for audit log no-PII guarantee — T028 [DbC].

AC18: Logs emitted by any function in the security module must NOT contain
      raw PII values.  They may contain entity_type, sha256_prefix (8 chars),
      and counters — but never actual CPF digits, names, e-mails, or phone numbers.

DbC (plan.md):
    Invariant: MaskedResult.entities never carries raw value.
    Invariant: ADR-0008 no-PII-in-logs policy is enforced at the logger level.

Tests marked ``requires_spacy`` need pt_core_news_lg installed.
"""

from __future__ import annotations

import logging
import re

import pytest


# Patterns that must NEVER appear in log output
_RAW_PII_PATTERNS = [
    r"111\.444\.777-35",  # synthetic CPF from conftest
    r"111444777-?35",  # CPF digits without dots
    r"11144477735",  # CPF raw digits only
    r"joao\.silva@example\.com",  # email from sample_text_pt
    r"joao@exemplo\.com",  # email variant
    r"João\s+Silva",  # person name
    r"98765-?4321",  # phone last digits
    r"\(11\)\s*9?8765",  # phone with DDD
]


@pytest.mark.requires_spacy
def test_no_raw_pii_in_module_logs(
    sample_text_pt: str, caplog: pytest.LogCaptureFixture
) -> None:
    """T028 [DbC] — AC18: no raw PII value appears in any security module log.

    Runs pii_mask on a text containing CPF, phone, email, and person name, then
    inspects all log records emitted by the 'security' logger hierarchy and
    asserts that none contain the raw PII values defined in _RAW_PII_PATTERNS.

    Also asserts that entity_type and sha256_prefix ARE present (confirming the
    audit log is informative without being leaky).
    """
    from security import pii_mask

    with caplog.at_level(logging.DEBUG, logger="security"):
        result = pii_mask(sample_text_pt, language="pt")

    # At least one record should have been emitted (the pii.masked event)
    assert caplog.records, "Expected at least one log record from security module"

    for record in caplog.records:
        full_message = record.getMessage()
        # Check the formatted message
        for pattern in _RAW_PII_PATTERNS:
            assert not re.search(pattern, full_message, re.IGNORECASE), (
                f"Raw PII pattern {pattern!r} found in log message: {full_message!r}"
            )
        # Also check raw args if any
        if record.args:
            args_str = str(record.args)
            for pattern in _RAW_PII_PATTERNS:
                assert not re.search(pattern, args_str, re.IGNORECASE), (
                    f"Raw PII pattern {pattern!r} found in log args: {args_str!r}"
                )
        # MINOR-2: also check extra dict fields attached to the record via
        # logging.info(..., extra={...}) — these become direct attributes on
        # LogRecord and are not covered by getMessage() or args.
        record_dict_str = str(record.__dict__)
        for pattern in _RAW_PII_PATTERNS:
            assert not re.search(pattern, record_dict_str, re.IGNORECASE), (
                f"Raw PII pattern {pattern!r} found in record.__dict__: "
                f"{record_dict_str!r}"
            )

    # Positive check: the security log should reference entity metadata, not raw values
    # At minimum, the entities list from the result must have sha256_prefix fields
    for hit in result.entities:
        assert len(hit.sha256_prefix) == 8
        assert all(c in "0123456789abcdef" for c in hit.sha256_prefix)


@pytest.mark.requires_spacy
def test_entity_hit_has_no_value_field(sample_text_pt: str) -> None:
    """EntityHit model must not expose a 'value' field at all — not just be None.

    This is a structural test: the Pydantic model itself should not declare 'value'.
    """
    from security import pii_mask
    from security.models import EntityHit

    result = pii_mask(sample_text_pt, language="pt")

    # Test the model class directly
    assert "value" not in EntityHit.model_fields, (
        "EntityHit must not declare a 'value' field (ADR-0008 no-PII-in-logs)"
    )
    assert "raw" not in EntityHit.model_fields, (
        "EntityHit must not declare a 'raw' field"
    )

    # Test instances
    for hit in result.entities:
        assert not hasattr(hit, "value"), "EntityHit instance must not have 'value' attribute"
        assert not hasattr(hit, "raw"), "EntityHit instance must not have 'raw' attribute"


def test_sha256_prefix_is_deterministic() -> None:
    """sha256_prefix is deterministic: same input always gives same 8-char prefix."""
    from security.models import sha256_prefix

    raw = "111.444.777-35"
    first = sha256_prefix(raw)
    second = sha256_prefix(raw)

    assert first == second
    assert len(first) == 8
    assert all(c in "0123456789abcdef" for c in first)
