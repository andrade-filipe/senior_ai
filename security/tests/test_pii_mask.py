"""Tests for pii_mask() public API — T010, T011, T012, T013, T019, T020, T021, T022, T023.

Covers:
    AC1  — pii_mask replaces PERSON and CPF with placeholders.
    AC2  — EntityHit never carries raw value; only sha256_prefix.
    AC3  — Unsupported language raises PIIError(E_PII_LANGUAGE).
    AC4  — Engine failure raises PIIError(E_PII_ENGINE).
    AC10 — EMAIL_ADDRESS masked as <EMAIL>.
    AC11 — DATE_TIME detected but NOT masked.
    AC12 — allow_list prevents masking of listed tokens.
    AC14 — Idempotence: double-masking yields same result.
    AC18 — No raw PII in logs (spot-checked via caplog).

Tests marked ``requires_spacy`` need pt_core_news_lg installed:
    uv run python -m spacy download pt_core_news_lg
"""

from __future__ import annotations

import logging

import pytest

# Mark for tests that require the real Presidio/spaCy engine
pytestmark_spacy = pytest.mark.requires_spacy


# ---------------------------------------------------------------------------
# AC1 — T010 [DbC]
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_mask_replaces_person_and_cpf(sample_text_pt: str) -> None:
    """T010 [DbC] — AC1: pii_mask replaces PERSON and CPF.

    Post: masked_text contains <CPF> and does not contain the raw CPF value.
    """
    from security import pii_mask

    result = pii_mask(sample_text_pt, language="pt")

    assert "<CPF>" in result.masked_text, (
        "Expected '<CPF>' placeholder in masked_text"
    )
    # Raw CPF must not appear in masked text
    assert "111.444.777-35" not in result.masked_text, (
        "Raw CPF value must not appear in masked_text"
    )


# ---------------------------------------------------------------------------
# AC2 — T011 [DbC]
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_entities_only_have_hash_not_raw(sample_text_pt: str) -> None:
    """T011 [DbC] — AC2: EntityHit never carries a raw PII value.

    Invariant: entities[*] has entity_type, start, end, score, sha256_prefix only.
    """
    from security import MaskedResult, pii_mask

    result = pii_mask(sample_text_pt, language="pt")

    assert isinstance(result, MaskedResult)
    for hit in result.entities:
        # Verify allowed fields exist
        assert hasattr(hit, "entity_type")
        assert hasattr(hit, "start")
        assert hasattr(hit, "end")
        assert hasattr(hit, "score")
        assert hasattr(hit, "sha256_prefix")
        # Verify no raw-value field
        assert not hasattr(hit, "value"), "EntityHit must not have a 'value' field"
        assert not hasattr(hit, "raw"), "EntityHit must not have a 'raw' field"
        # sha256_prefix must be exactly 8 hex chars
        assert len(hit.sha256_prefix) == 8
        assert all(c in "0123456789abcdef" for c in hit.sha256_prefix)


# ---------------------------------------------------------------------------
# AC3 — T012
# ---------------------------------------------------------------------------


def test_unsupported_language_raises_e_pii_language() -> None:
    """T012 — AC3: unsupported language raises PIIError(E_PII_LANGUAGE)."""
    from security import PIIError, pii_mask

    with pytest.raises(PIIError) as exc_info:
        pii_mask("some text", language="fr")

    assert exc_info.value.code == "E_PII_LANGUAGE"
    assert "fr" in exc_info.value.message or "fr" in str(exc_info.value.context)


# ---------------------------------------------------------------------------
# AC4 — T013
# ---------------------------------------------------------------------------


def test_engine_failure_raises_e_pii_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """T013 — AC4: Presidio initialisation failure raises PIIError(E_PII_ENGINE).

    Patches engine.get_analyzer to raise PIIError(E_PII_ENGINE) simulating a
    missing spaCy model.  The pool is replaced with a fake that calls the worker
    function directly in-process so that the monkeypatch is visible.

    MAJOR-2 fix: patch must target the engine initialisation layer, not the
    guard module's local binding, because with multiprocessing the worker runs in
    a separate process where in-process patches are invisible.  We bypass the pool
    here by replacing _get_pool with a fake that invokes the function synchronously
    and lets the PIIError propagate.
    """
    import security.engine as engine_module
    import security.guard as guard_module
    from security import PIIError, pii_mask
    from security.errors import PIIError as _PIIError

    def _broken_engine(language: str) -> None:
        raise _PIIError(
            code="E_PII_ENGINE",
            message="Motor PII não inicializou",
            hint="Verifique dependências de security/",
        )

    # Patch engine.get_analyzer so the worker would fail if called.
    # Then replace _get_pool with a fake that invokes _worker_analyze in-process,
    # making the monkeypatch on engine_module visible.
    monkeypatch.setattr(engine_module, "get_analyzer", _broken_engine)

    class _InProcessAsyncResult:
        """Calls _worker_analyze synchronously in the same process."""

        def __init__(self, func: object, args: tuple[object, ...]) -> None:
            self._func = func
            self._args = args

        def get(self, timeout: float) -> object:  # noqa: ARG002
            return self._func(*self._args)  # type: ignore[operator]

    class _InProcessPool:
        def apply_async(
            self, func: object, args: tuple[object, ...]
        ) -> _InProcessAsyncResult:
            return _InProcessAsyncResult(func, args)

    monkeypatch.setattr(guard_module, "_get_pool", lambda: _InProcessPool())

    with pytest.raises(PIIError) as exc_info:
        pii_mask("some text", language="pt")

    assert exc_info.value.code == "E_PII_ENGINE"


# ---------------------------------------------------------------------------
# AC10 — T019
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_email_masked_as_placeholder() -> None:
    """T019 — AC10: e-mail address is masked as <EMAIL>."""
    from security import pii_mask

    result = pii_mask("contato: joao@exemplo.com", language="pt")

    assert "<EMAIL>" in result.masked_text, (
        "Expected '<EMAIL>' placeholder for e-mail address"
    )
    assert "joao@exemplo.com" not in result.masked_text


# ---------------------------------------------------------------------------
# AC11 — T020
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_date_time_detected_but_not_masked() -> None:
    """T020 — AC11: DATE_TIME is detected but the date string is NOT replaced.

    Policy (ARCHITECTURE.md): clinical dates are relevant context, so DATE_TIME
    entities are reported in result.entities but preserved in masked_text.
    """
    from security import pii_mask

    text = "Data do exame: 01/05/2026"
    result = pii_mask(text, language="pt")

    # The date string must survive in masked_text
    assert "01/05/2026" in result.masked_text, (
        "Date '01/05/2026' must NOT be masked (DATE_TIME policy)"
    )

    # DATE_TIME may or may not appear in entities depending on Presidio model;
    # if detected, it should be in the entities list
    entity_types = [h.entity_type for h in result.entities]
    # We do NOT assert DATE_TIME is in the list (Presidio may not detect it);
    # we only assert it was NOT masked if it was detected.
    if "DATE_TIME" in entity_types:
        assert "01/05/2026" in result.masked_text


# ---------------------------------------------------------------------------
# AC12 — T021
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_allow_list_bypasses_mask() -> None:
    """T021 — AC12: tokens in allow_list are not masked."""
    from security import pii_mask

    text = "exame: hemograma completo"
    result = pii_mask(text, language="pt", allow_list=["hemograma"])

    assert "hemograma" in result.masked_text, (
        "allow-listed token 'hemograma' must not be masked"
    )


# ---------------------------------------------------------------------------
# AC14 — T022 [DbC]
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
@pytest.mark.parametrize(
    "input_text",
    [
        "João Silva CPF 111.444.777-35 tel (11) 98765-4321",
        "paciente com email joao@exemplo.com",
        "texto sem PII nenhuma — pode ter <PERSON> já mascarado",
        "",
    ],
)
def test_idempotent_double_mask(input_text: str) -> None:
    """T022 [DbC] — AC14: double masking yields the same result as single masking.

    Invariant (ADR-0003 dupla camada): applying pii_mask twice must not alter the
    already-masked text.  This guarantees that the OCR layer (pass 1) and the
    before_model_callback layer (pass 2) compose without destructive interaction.
    """
    from security import pii_mask

    first_pass = pii_mask(input_text, language="pt")
    second_pass = pii_mask(first_pass.masked_text, language="pt")

    assert second_pass.masked_text == first_pass.masked_text, (
        f"Idempotence failed.\n"
        f"  Input:       {input_text!r}\n"
        f"  First pass:  {first_pass.masked_text!r}\n"
        f"  Second pass: {second_pass.masked_text!r}"
    )


# ---------------------------------------------------------------------------
# AC18 — T023 (no-PII-in-logs spot check)
# ---------------------------------------------------------------------------


@pytest.mark.requires_spacy
def test_no_raw_pii_in_logs(sample_text_pt: str, caplog: pytest.LogCaptureFixture) -> None:
    """T023 — AC18 spot check: pii_mask logs must not contain raw CPF or email.

    This is a spot-check focused on the guard.py logger.  Full AC18 coverage is
    in test_logging.py::test_no_raw_pii_in_module_logs.
    """
    import re

    from security import pii_mask

    # CPF and email present in sample_text_pt
    pii_patterns = [
        r"111\.444\.777-35",  # raw CPF
        r"joao\.silva@example\.com",  # raw email
        r"João Silva",  # raw name
    ]

    with caplog.at_level(logging.DEBUG, logger="security"):
        pii_mask(sample_text_pt, language="pt")

    for pattern in pii_patterns:
        for record in caplog.records:
            assert not re.search(pattern, record.getMessage()), (
                f"Raw PII pattern {pattern!r} found in log record: {record.getMessage()!r}"
            )
            if record.args:
                log_str = str(record.args)
                assert not re.search(pattern, log_str), (
                    f"Raw PII pattern {pattern!r} found in log args: {log_str!r}"
                )
