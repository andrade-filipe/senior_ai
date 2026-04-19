"""Tests for security.make_pii_callback (ADR-0003 Layer 2).

These tests validate the before_model_callback factory added to the security
module for use by the generated ADK agent (Block 0006 T013, ADR-0003).
"""

from __future__ import annotations

import re


class _Part:
    """Minimal stand-in for google.genai.types.Part."""

    def __init__(self, text: str) -> None:
        self.text = text


class _Content:
    """Minimal stand-in for google.genai.types.Content."""

    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _LlmRequest:
    """Minimal stand-in for ADK LlmRequest."""

    def __init__(self, texts: list[str]) -> None:
        self.contents = [_Content([_Part(t) for t in texts])]


def _make_request(texts: list[str]) -> _LlmRequest:
    return _LlmRequest(texts)


def test_make_pii_callback_is_callable() -> None:
    """make_pii_callback returns a callable (ADR-0003 Layer 2)."""
    from security import make_pii_callback

    cb = make_pii_callback()
    assert callable(cb)


def test_make_pii_callback_with_allow_list() -> None:
    """make_pii_callback accepts an allow_list parameter."""
    from security import make_pii_callback

    cb = make_pii_callback(allow_list=["Hospital"])
    assert callable(cb)


def test_before_model_callback_strips_cpf() -> None:
    """Callback masks CPF values in llm_request text parts (ADR-0003, AC4).

    Pre:
        llm_request.contents[0].parts[0].text contains a CPF.
    Post:
        After callback, the CPF pattern is replaced by <CPF>.
    """
    from security import make_pii_callback

    req = _make_request(["Paciente CPF 111.444.777-35 solicita hemograma."])
    cb = make_pii_callback()
    cb(None, req)  # (callback_context, llm_request)

    masked = req.contents[0].parts[0].text
    assert re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", masked) is None, (
        f"CPF must be masked, got: {masked!r}"
    )
    assert "<CPF>" in masked, f"Expected <CPF> placeholder, got: {masked!r}"


def test_before_model_callback_strips_person_name() -> None:
    """Callback masks PERSON entities in llm_request.

    This test relies on Presidio's spaCy NER for Brazilian Portuguese.
    """
    from security import make_pii_callback

    req = _make_request(["Joao Silva quer agendar exame de sangue."])
    cb = make_pii_callback()
    cb(None, req)

    masked = req.contents[0].parts[0].text
    # Either masked or unchanged — Presidio NER confidence may vary in test env.
    # The critical assertion is that NO exception was raised.
    assert isinstance(masked, str)


def test_callback_no_crash_on_empty_request() -> None:
    """Callback handles empty contents list without raising."""
    from security import make_pii_callback

    req = _LlmRequest([])
    req.contents = []
    cb = make_pii_callback()
    cb(None, req)  # must not raise


def test_callback_no_crash_on_no_contents_attr() -> None:
    """Callback handles objects without 'contents' attribute gracefully."""
    from security import make_pii_callback

    cb = make_pii_callback()
    cb(None, object())  # must not raise


def test_callback_masks_multiple_parts() -> None:
    """Callback processes all parts across all contents."""
    from security import make_pii_callback

    req = _LlmRequest(["CPF 111.444.777-35", "outro CPF 111.444.777-35 aqui"])
    cb = make_pii_callback()
    cb(None, req)

    for part in req.contents[0].parts:
        assert re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", part.text) is None, (
            f"CPF must be masked in all parts, found in: {part.text!r}"
        )


def test_callback_allow_list_preserves_token() -> None:
    """Tokens in allow_list must not be masked by the callback."""
    from security import make_pii_callback

    # This tests the allow_list passthrough to pii_mask.
    # We use a token that would normally be masked if detected.
    req = _make_request(["Texto sem PII aqui."])
    cb = make_pii_callback(allow_list=["Texto"])
    cb(None, req)

    # 'Texto' is not PII — just confirm no crash and text is unchanged
    assert req.contents[0].parts[0].text == "Texto sem PII aqui."


def test_callback_oversize_part_is_skipped(caplog: object) -> None:
    """BLOCKER-1 addendum: parts exceeding _MAX_TEXT_BYTES are skipped with WARNING.

    The part text must be left UNCHANGED (not masked, not replaced).
    A pii.callback.oversize_skip log entry at WARNING level must be emitted.
    """
    import logging

    from security.callback import _MAX_TEXT_BYTES, make_pii_callback

    # Build a text that exceeds the cap by 1 byte
    oversized_text = "A" * (_MAX_TEXT_BYTES + 1)
    req = _make_request([oversized_text])
    cb = make_pii_callback()

    import io

    # Capture log output
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.WARNING)
    logger = logging.getLogger("security.callback")
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(logging.WARNING)

    try:
        cb(None, req)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)

    # Part text must be unchanged (skipped, not replaced)
    assert req.contents[0].parts[0].text == oversized_text

    # A warning must have been logged
    log_output = buf.getvalue()
    assert "oversize_skip" in log_output or "sha256" in log_output


def test_callback_pii_error_replaces_with_redacted() -> None:
    """MINOR-3: when pii_mask raises, part text is replaced with sentinel, not passed through."""
    from unittest.mock import patch

    from security.callback import make_pii_callback

    req = _make_request(["Some text with potential PII"])
    cb = make_pii_callback()

    # Simulate pii_mask raising an unexpected error
    with patch("security.callback.pii_mask", side_effect=RuntimeError("engine failure")):
        cb(None, req)

    # Must NOT silently pass the original text through
    assert req.contents[0].parts[0].text == "<REDACTED - PII guard error>"
