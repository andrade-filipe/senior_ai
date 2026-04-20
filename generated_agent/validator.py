"""Validator-pass via google.genai direct — spec 0009 Camada C.

Opt-in safety net. When the primary parser in __main__._parse_runner_output
fails to validate the agent's final output against RunnerResult, and the
AGENT_VALIDATOR_PASS_ENABLED flag is set, the CLI makes a second, minimal
Gemini call to reformat the raw text against the canonical schema.

Invariant: this function NEVER raises to the caller. Any failure (timeout,
HTTP error, empty response, invalid JSON) returns None so the caller falls
back to the original E_AGENT_OUTPUT_INVALID exit-3 behavior. This keeps the
validator from masking genuine bugs in the primary agent.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash-lite"
_DEFAULT_MAX_INPUT_BYTES = 16384
_DEFAULT_TIMEOUT_S = 15.0

_PROMPT_TEMPLATE = """\
Voce e um reformatador estrutural. Dado o texto a seguir (saida bruta de outro agente),
devolva UM UNICO objeto JSON que satisfaz o schema abaixo. Nao invente campos,
nao use markdown, nao adicione texto antes ou depois.

Se o texto descreve sucesso (tem um appointment_id), use status="success".
Se o texto descreve falha, use status="error" com um envelope error.

SCHEMA (simplificado):
{{
  "status": "success",
  "exams": [{{"name": str, "code": str, "score": float, "inconclusive": bool}}],
  "appointment_id": str,
  "scheduled_for": str
}}
OU
{{
  "status": "error",
  "error": {{"code": str, "message": str, "hint": str|null}}
}}

TEXTO:
{raw}
"""


def _build_client() -> Any:
    """Construct a google.genai.Client lazily (keeps imports cheap in tests).

    Raises:
        ImportError: when google.genai is not installed (caller catches).
    """
    from google import genai  # noqa: PLC0415

    return genai.Client()


def _run_validator_pass(raw_text: str, correlation_id: str) -> str | None:
    """Reformat drifting agent output against RunnerResult schema.

    Pre:
        raw_text is a non-empty string.

    Post:
        Returns a JSON string (not validated here — the caller re-parses) on
        success, or None on any failure.

    Invariant:
        Never raises. Timeouts and HTTP errors become None + a warning log.

    Args:
        raw_text: Agent's final output that failed the primary parser.
        correlation_id: UUID to tie the log line back to the parent run.

    Returns:
        Reformatted JSON string or None.
    """
    if not raw_text:
        return None

    max_bytes = int(os.environ.get("VALIDATOR_MAX_INPUT_BYTES", _DEFAULT_MAX_INPUT_BYTES))
    if len(raw_text.encode("utf-8")) > max_bytes:
        _LOGGER.warning(
            "agent.validator.skipped",
            extra={
                "event": "agent.validator.skipped",
                "correlation_id": correlation_id,
                "reason": "input_too_large",
                "input_bytes": len(raw_text.encode("utf-8")),
                "max_bytes": max_bytes,
            },
        )
        return None

    model = os.environ.get("VALIDATOR_MODEL", _DEFAULT_MODEL)

    _LOGGER.info(
        "agent.validator.start",
        extra={
            "event": "agent.validator.start",
            "correlation_id": correlation_id,
            "model": model,
        },
    )

    try:
        client = _build_client()
        response = client.models.generate_content(
            model=model,
            contents=_PROMPT_TEMPLATE.format(raw=raw_text),
        )
    except Exception as exc:  # noqa: BLE001 — invariant: never raise
        _LOGGER.warning(
            "agent.validator.error",
            extra={
                "event": "agent.validator.error",
                "correlation_id": correlation_id,
                "error": str(exc),
            },
        )
        return None

    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        _LOGGER.warning(
            "agent.validator.empty",
            extra={
                "event": "agent.validator.empty",
                "correlation_id": correlation_id,
            },
        )
        return None

    _LOGGER.info(
        "agent.validator.applied",
        extra={
            "event": "agent.validator.applied",
            "correlation_id": correlation_id,
        },
    )
    return text
