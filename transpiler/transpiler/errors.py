"""Transpiler error hierarchy and serialization helpers.

All public exceptions in the transpiler module inherit from ChallengeError.
Error messages directed at the user are written in PT-BR. Internal log
messages and code identifiers use English.

Shape canônico (ADR-0008 § Shape canônico da resposta de erro):
    {code, message, hint, path, context}
"""

from __future__ import annotations

from typing import Any


class ChallengeError(Exception):
    """Base exception for all challenge services.

    Carries the five-field canonical error shape defined in ADR-0008.

    Attributes:
        code: Stable error identifier (e.g. 'E_TRANSPILER_SCHEMA'). Never reused across modules.
        message: Human-readable description in PT-BR. Explains what went wrong.
        hint: Optional corrective action for the user in PT-BR.
              Must be provided when the user can act on the error.
        path: Optional dot-notation field path that caused the error (e.g. 'mcp_servers.0.url').
        context: Optional dict with diagnostic details. Must never contain raw PII values.
    """

    def __init__(
        self,
        code: str,
        message: str,
        hint: str | None = None,
        path: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.path = path
        self.context = context

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, message={self.message!r}, "
            f"hint={self.hint!r}, path={self.path!r})"
        )


class TranspilerError(ChallengeError):
    """Exception raised by the transpiler module.

    All transpiler errors carry code='E_TRANSPILER_SCHEMA', 'E_TRANSPILER_RENDER',
    or 'E_TRANSPILER_SYNTAX' as defined in docs/ARCHITECTURE.md § Taxonomia de erros.
    """


def format_validation_error(
    exc: Exception,
    first_loc: tuple[int | str, ...],
) -> tuple[str | None, dict[str, Any]]:
    """Extract `loc` path string and wrap the Pydantic ValidationError as a context dict.

    User-facing PT-BR messages are built separately by the caller.

    Args:
        exc: The original pydantic.ValidationError or any exception.
        first_loc: The location tuple from the first Pydantic error entry.

    Returns:
        A tuple of (path_string, context_dict) where path_string may be None
        when first_loc is empty.

    Note:
        Only the first validation error is reported for simplicity.
        This behaviour is documented here so callers are not surprised.
        Rationale: showing one clear error at a time is more actionable
        than a wall of validation failures.
    """
    path_str = ".".join(str(p) for p in first_loc) if first_loc else None
    context: dict[str, Any] = {"pydantic_error": str(exc)}
    return path_str, context


def format_challenge_error(exc: ChallengeError) -> dict[str, Any]:
    """Serialize a ChallengeError to the canonical five-field dict (ADR-0008).

    The returned dict is suitable for JSON serialization, CLI stderr output,
    and HTTP response bodies.

    Args:
        exc: Any ChallengeError (or subclass) instance.

    Returns:
        Dict with exactly five keys: code, message, hint, path, context.
        Optional fields (hint, path, context) are present with None when absent.

    Invariant:
        Return dict always contains exactly the keys {code, message, hint, path, context}.
    """
    return {
        "code": exc.code,
        "message": exc.message,
        "hint": exc.hint,
        "path": exc.path,
        "context": exc.context,
    }
