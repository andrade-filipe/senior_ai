"""PII guard error hierarchy.

All public exceptions in the security module inherit from ChallengeError.
Error codes are defined in docs/ARCHITECTURE.md § Taxonomia de erros and
docs/adr/0008-robust-validation-policy.md.

Error messages directed at the user are written in PT-BR.
Internal log messages and code identifiers use English.

Note on ChallengeError (MAJOR-1 — drift acknowledged):
    Security is a standalone package (ADR-0005 — one pyproject.toml per service).
    ChallengeError is re-declared here with the identical interface as in
    transpiler/transpiler/errors.py so that consumers of security/ do not need
    to depend on the transpiler package.  Both declarations honour ADR-0008
    canonical shape: {code, message, hint, path, context}.

    Drift risk: if the canonical shape in transpiler/transpiler/errors.py changes,
    this re-declaration must be updated manually.  A follow-up task should evaluate
    extracting ChallengeError into a shared library (e.g. challenge_base or similar)
    to eliminate the duplication.  Tracked as a post-MVP concern; the re-declaration
    is intentional and documented per MAJOR-1 code-review finding.
"""

from __future__ import annotations

from typing import Any


class ChallengeError(Exception):
    """Base exception for all challenge services.

    Carries the five-field canonical error shape defined in ADR-0008.

    Attributes:
        code: Stable error identifier (e.g. 'E_PII_ENGINE'). Never reused across modules.
        message: Human-readable description in PT-BR. Explains what went wrong.
        hint: Optional corrective action for the user in PT-BR.
              Must be provided when the user can act on the error.
        path: Optional dot-notation field path that caused the error.
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


class PIIError(ChallengeError):
    """Exception raised by the security / PII guard module.

    Valid codes (docs/ARCHITECTURE.md § Taxonomia de erros + ADR-0008):
        E_PII_ENGINE         — Presidio / spaCy failed to initialise.
        E_PII_LANGUAGE       — Unsupported language code supplied.
        E_PII_TEXT_SIZE      — Input text exceeds 100 KB cap (ADR-0008).
        E_PII_ALLOW_LIST_SIZE — allow_list exceeds 1 000-item cap (ADR-0008).
        E_PII_TIMEOUT        — pii_mask processing exceeded 5-second timeout (ADR-0008).
    """
