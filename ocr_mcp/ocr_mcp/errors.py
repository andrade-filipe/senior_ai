"""OCR MCP error types (ADR-0008 canonical shape).

All errors raised by this module carry:
    code: str       — stable E_* code from ARCHITECTURE.md table
    message: str    — user-facing message in PT-BR
    hint: str       — actionable suggestion for the caller
    context: dict   — non-PII metadata (bytes, caps, etc.)

Hierarchy:
    ChallengeError (base, from ARCHITECTURE.md)
    └── OcrError
"""

from __future__ import annotations

from typing import Any


class ChallengeError(Exception):
    """Base error for all modules in the Desafio Técnico Sênior IA project.

    Attributes:
        code: Stable E_* code from ARCHITECTURE.md § Taxonomia de erros.
        message: User-facing message in PT-BR.
        hint: Actionable correction suggestion.
        context: Optional non-PII diagnostic data (counts, caps, entity_type, etc.).
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
        """Serialize to the canonical ADR-0008 error shape.

        Returns:
            Dict with keys: code, message, hint, context.
            hint is omitted when empty. context is omitted when empty.
        """
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            result["hint"] = self.hint
        if self.context:
            result["context"] = self.context
        return result


class OcrError(ChallengeError):
    """OCR MCP specific errors.

    Valid codes:
        E_OCR_IMAGE_TOO_LARGE  — decoded bytes exceed 5 MB cap (AC15)
        E_OCR_INVALID_INPUT    — image_base64 is not valid base64 (AC16)
        E_OCR_TIMEOUT          — OCR processing exceeded 5 s (AC17)
    """
