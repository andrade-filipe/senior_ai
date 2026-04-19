"""Error codes and canonical error response schema for the scheduling API.

All 4xx/5xx responses use ErrorBody wrapped in ErrorEnvelope — never FastAPI's
default ``{"detail": ...}`` shape (AC16, ADR-0008 § Shape canônico).

Taxonomy (module-owned codes, per ARCHITECTURE.md § Taxonomia de erros):
  E_API_NOT_FOUND          — resource does not exist (GET /{id})
  E_API_VALIDATION         — body/query invalid; pattern mismatch; caps
  E_API_PAYLOAD_TOO_LARGE  — HTTP body > 256 KB (AC10)
  E_API_TIMEOUT            — request processing exceeded 10 s (AC15)
  E_API_INTERNAL           — catch-all 500 (unclassified server error)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Stable error codes owned by this module
# ---------------------------------------------------------------------------

E_API_NOT_FOUND: str = "E_API_NOT_FOUND"
E_API_VALIDATION: str = "E_API_VALIDATION"
E_API_PAYLOAD_TOO_LARGE: str = "E_API_PAYLOAD_TOO_LARGE"
E_API_TIMEOUT: str = "E_API_TIMEOUT"
E_API_INTERNAL: str = "E_API_INTERNAL"


# ---------------------------------------------------------------------------
# Canonical error body (ADR-0008 § Shape canônico)
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    """Inner error object — shape mandated by ADR-0008.

    Invariant: ``code`` is always one of the stable E_API_* constants.
    ``context`` never carries PII (ADR-0003).
    """

    code: str
    message: str
    hint: str | None = None
    path: str | None = None
    context: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    """HTTP error response envelope (AC16).

    Wraps ``ErrorBody`` with the ``correlation_id`` so clients can
    correlate API errors with log lines (ADR-0008 § Correlation ID).
    """

    error: ErrorBody
    correlation_id: str


def make_error_envelope(
    code: str,
    message: str,
    correlation_id: str,
    hint: str | None = None,
    path: str | None = None,
    context: dict[str, Any] | None = None,
) -> ErrorEnvelope:
    """Build a canonical ErrorEnvelope ready for JSON serialization.

    Args:
        code: One of the stable E_API_* constants.
        message: Human-readable description (PT-BR per ARCHITECTURE taxonomy).
        correlation_id: Current request correlation ID from context var.
        hint: Actionable hint for the caller (required when caller can act).
        path: Dot-notation field path that triggered the error.
        context: Safe debugging metadata — never PII.

    Returns:
        ErrorEnvelope instance.
    """
    body = ErrorBody(code=code, message=message, hint=hint, path=path, context=context)
    return ErrorEnvelope(error=body, correlation_id=correlation_id)
