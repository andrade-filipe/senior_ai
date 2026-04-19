"""Tests for error classes in security.errors.

Validates that PIIError carries the canonical five-field shape (ADR-0008)
and that all E_PII_* codes are correctly formulated.
"""

from __future__ import annotations


def test_pii_error_carries_code_and_message() -> None:
    """PIIError stores code, message, hint, path, and context."""
    from security.errors import PIIError

    err = PIIError(
        code="E_PII_LANGUAGE",
        message="Idioma 'fr' não suportado",
        hint="Use 'pt' ou 'en'",
        context={"language": "fr"},
    )
    assert err.code == "E_PII_LANGUAGE"
    assert "fr" in err.message
    assert err.hint is not None
    assert err.context == {"language": "fr"}


def test_pii_error_is_challenge_error() -> None:
    """PIIError must be a subclass of ChallengeError (ADR-0008 hierarchy)."""
    from security.errors import ChallengeError, PIIError

    err = PIIError(code="E_PII_ENGINE", message="Motor falhou")
    assert isinstance(err, ChallengeError)
    assert isinstance(err, Exception)


def test_pii_error_repr_contains_code() -> None:
    """PIIError repr shows the error code."""
    from security.errors import PIIError

    err = PIIError(code="E_PII_TEXT_SIZE", message="Texto excede 100 KB")
    assert "E_PII_TEXT_SIZE" in repr(err)


def test_challenge_error_optional_fields_default_none() -> None:
    """hint, path, and context default to None when not provided."""
    from security.errors import ChallengeError

    err = ChallengeError(code="E_SOMETHING", message="msg")
    assert err.hint is None
    assert err.path is None
    assert err.context is None
