"""Tests for transpiler.errors — canonical error shape (AC13).

Validates that format_challenge_error() emits the five-field canonical
shape defined in ADR-0008 § Shape canônico da resposta de erro.
"""

import pytest

from transpiler import TranspilerError, format_challenge_error


def test_format_challenge_error_shape() -> None:
    """AC13 — TranspilerError serializes to the five-field canonical shape.

    Shape defined in ADR-0008:
        code, message, hint, path, context
    All five keys must be present (values may be None for optional fields).
    """
    err = TranspilerError(
        code="E_TRANSPILER_SCHEMA",
        message="Campo `model` inválido: 'gpt-4' não é um valor aceito",
        hint="Use 'gemini-2.5-flash'. Outros modelos não são suportados.",
        path="model",
        context={"received": "gpt-4", "allowed": ["gemini-2.5-flash"]},
    )

    shape = format_challenge_error(err)

    required_keys = {"code", "message", "hint", "path", "context"}
    assert required_keys == set(shape.keys()), (
        f"Shape must contain exactly {required_keys}, got {set(shape.keys())}"
    )
    assert shape["code"] == "E_TRANSPILER_SCHEMA"
    assert shape["message"] == "Campo `model` inválido: 'gpt-4' não é um valor aceito"
    assert shape["hint"] is not None
    assert shape["path"] == "model"
    assert isinstance(shape["context"], dict)


def test_format_challenge_error_optional_fields_none() -> None:
    """format_challenge_error must include path and context even when None."""
    err = TranspilerError(
        code="E_TRANSPILER_SCHEMA",
        message="Spec inválido",
        hint=None,
        path=None,
        context=None,
    )

    shape = format_challenge_error(err)

    assert "path" in shape
    assert "context" in shape
    assert shape["path"] is None
    assert shape["context"] is None
