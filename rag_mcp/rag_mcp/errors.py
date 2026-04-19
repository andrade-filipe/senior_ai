"""RAG MCP error types (ADR-0008 canonical shape).

Hierarchy:
    ChallengeError (base)
    ├── CatalogError  — raised by catalog.load() on invalid CSV
    └── RagError      — raised by tools at runtime
"""

from __future__ import annotations

from typing import Any


class ChallengeError(Exception):
    """Base error for all challenge modules (ARCHITECTURE.md § Taxonomia de erros).

    Attributes:
        code: Stable E_* error code.
        message: User-facing message in PT-BR.
        hint: Actionable correction suggestion.
        context: Optional non-PII diagnostic data.
    """

    def __init__(
        self,
        code: str,
        message: str,
        hint: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.context: dict[str, Any] = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to canonical ADR-0008 error shape.

        Returns:
            Dict with code, message, and optionally hint and context.
        """
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            result["hint"] = self.hint
        if self.context:
            result["context"] = self.context
        return result


class CatalogError(ChallengeError):
    """Raised by catalog.load() when the CSV is invalid or missing.

    Valid code:
        E_CATALOG_LOAD_FAILED — file missing, invalid header, duplicate code, encoding error.

    The message must cite the line number and/or value for duplicate-code errors (AC14, AC20).
    """


class RagError(ChallengeError):
    """Raised by RAG tools at runtime.

    Valid codes:
        E_RAG_QUERY_TOO_LARGE — exam_name exceeds 500 chars (AC18)
        E_RAG_QUERY_EMPTY     — exam_name is empty/whitespace after strip() (AC19)
        E_RAG_TIMEOUT         — search_exam_code exceeded 2 s (AC21)
    """
