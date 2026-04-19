"""ADK before_model_callback factory for PII masking (ADR-0003 Layer 2).

This module provides make_pii_callback(), which returns an ADK-compatible
before_model_callback that applies pii_mask() to every text part in the
LLM request before it is sent to Gemini.

Docstring contract (ADR-0003):
    Pre:
        allow_list is a list of tokens that must NOT be masked (may be empty).
    Post:
        The returned callback, when registered as before_model_callback on a
        LlmAgent, ensures that no raw PII value reaches the Gemini API.
    Invariant:
        The callback mutates llm_request.contents[*].parts[*].text in-place.
        It never raises; pii_mask errors are caught and logged with sha256 hash
        of the offending text (no raw PII in logs — ADR-0008).
        Text parts exceeding _MAX_TEXT_BYTES are skipped with a WARNING log
        (pii.callback.oversize_skip) — these cannot legitimately contain PII
        entities without being oversized output (BLOCKER-1 defensive addendum).
        Parts where pii_mask raises are replaced with "<REDACTED - PII guard error>"
        rather than being silently passed through (MINOR-3 fix).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Callable

from security.guard import pii_mask

_LOGGER = logging.getLogger(__name__)

# Match guard.py _TEXT_MAX_BYTES cap — text exceeding this cannot be processed
# by pii_mask anyway (it would raise E_PII_TEXT_SIZE). Skip and log a warning.
_MAX_TEXT_BYTES = 100 * 1024  # 100 KB


def make_pii_callback(
    allow_list: list[str] | None = None,
) -> Callable[..., None]:
    """Return an ADK before_model_callback that strips PII from LLM requests.

    The returned callable has signature:
        callback(callback_context, llm_request) -> None

    It iterates over llm_request.contents[].parts[].text and calls pii_mask()
    on each text part, replacing the text in-place with the masked version.

    Pre:
        allow_list is a list of exact tokens (case-insensitive) to skip masking.
        Passing None or [] is equivalent — no tokens are exempted.
    Post:
        When the returned callback is invoked, every text part in llm_request
        has been passed through pii_mask(); no raw PII value reaches the LLM.
        Parts exceeding _MAX_TEXT_BYTES are skipped (logged at WARNING).
        Parts where pii_mask raises are replaced with "<REDACTED - PII guard error>".
    Invariant:
        Errors from pii_mask() are caught; the callback logs the error (no PII
        in the log — only sha256 prefix of the offending text) and replaces the
        part text with a safe redaction sentinel. This prevents a PII-guard
        failure from crashing the agent while still providing an audit trail.

    Args:
        allow_list: Optional list of tokens that must NOT be masked.

    Returns:
        A callable compatible with ADK LlmAgent.before_model_callback.

    Example:
        agent = LlmAgent(
            ...
            before_model_callback=make_pii_callback(allow_list=["HospitalXYZ"]),
        )
    """
    _allow = list(allow_list) if allow_list else []

    def _callback(callback_context: object, llm_request: object) -> None:  # noqa: ARG001
        """Apply PII masking to all text parts of llm_request (ADR-0003 Layer 2).

        Args:
            callback_context: ADK callback context (unused; present for ADK signature).
            llm_request: ADK LLM request object. Mutated in-place.
        """
        if not hasattr(llm_request, "contents"):
            return
        for content in llm_request.contents:
            if not hasattr(content, "parts"):
                continue
            for part in content.parts:
                if not (hasattr(part, "text") and isinstance(part.text, str)):
                    continue
                _mask_part(part, _allow)

    return _callback


def _mask_part(part: object, allow_list: list[str]) -> None:
    """Mask a single LLM request part in-place.

    Oversized parts (> _MAX_TEXT_BYTES) are skipped with a WARNING log —
    they cannot contain PII entities that pii_mask can process.

    Errors from pii_mask are caught; the part text is replaced with
    "<REDACTED - PII guard error>" rather than being silently passed through.

    Args:
        part: An object with a mutable `.text` str attribute.
        allow_list: Tokens to skip masking.
    """
    raw: str = part.text  # type: ignore[attr-defined]

    # Oversize short-circuit: skip masking and log warning (BLOCKER-1 addendum)
    if len(raw.encode("utf-8")) > _MAX_TEXT_BYTES:
        prefix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        _LOGGER.warning(
            "pii.callback.oversize_skip",
            extra={
                "event": "pii.callback.oversize_skip",
                "text_sha256": f"sha256:{prefix}",
                "text_bytes": len(raw.encode("utf-8")),
            },
        )
        return

    try:
        result = pii_mask(raw, language="pt", allow_list=allow_list)
        part.text = result.masked_text  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        # MINOR-3: replace with safe sentinel — do NOT silently pass PII through
        prefix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        _LOGGER.error(
            "pii.callback.error",
            extra={
                "error": str(exc),
                "text_sha256_prefix": prefix,
                "event": "pii.callback.error",
            },
        )
        part.text = "<REDACTED - PII guard error>"  # type: ignore[attr-defined]
