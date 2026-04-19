"""Tests for guardrail checks in pii_mask — T025, T026, T027.

AC15 — text > 100 KB raises PIIError(E_PII_TEXT_SIZE).
AC16 — allow_list > 1000 items raises PIIError(E_PII_ALLOW_LIST_SIZE).
         Note: spec AC16 stated 50 items; ADR-0008 (normative cross-service policy)
         sets the cap at 1000 items.  ADR-0008 governs over spec-level detail.
AC17 — processing timeout > 5 s raises PIIError(E_PII_TIMEOUT).
"""

from __future__ import annotations

import multiprocessing as mp
import time

import pytest


# ---------------------------------------------------------------------------
# AC15 — T025 [DbC]
# ---------------------------------------------------------------------------


def test_text_over_100kb_rejected() -> None:
    """T025 [DbC] — AC15: text larger than 100 KB is rejected before Presidio.

    Pre (pii_mask): len(text.encode('utf-8')) <= 100 KB.
    """
    from security import PIIError, pii_mask

    # Generate a string larger than 100 KB
    big_text = "a" * (100 * 1024 + 1)
    assert len(big_text.encode("utf-8")) > 100 * 1024

    with pytest.raises(PIIError) as exc_info:
        pii_mask(big_text, language="pt")

    err = exc_info.value
    assert err.code == "E_PII_TEXT_SIZE", f"Expected E_PII_TEXT_SIZE, got {err.code}"
    assert err.context is not None
    assert err.context["bytes_received"] > 100 * 1024


def test_text_at_100kb_boundary_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text at exactly 100 KB boundary must NOT raise a size error.

    The pool is mocked so the test does not require spaCy model installation.
    """
    from security import MaskedResult, pii_mask
    import security.guard as guard_module

    text_at_cap = "a" * (100 * 1024)
    assert len(text_at_cap.encode("utf-8")) == 100 * 1024

    _mock_result = MaskedResult(masked_text=text_at_cap, entities=[])

    class _FakeAsyncResult:
        def get(self, timeout: float) -> MaskedResult:  # noqa: ARG002
            return _mock_result

    class _FakePool:
        def apply_async(self, func: object, args: object) -> _FakeAsyncResult:  # noqa: ARG002
            return _FakeAsyncResult()

    monkeypatch.setattr(guard_module, "_get_pool", lambda: _FakePool())

    result = pii_mask(text_at_cap, language="pt")
    assert isinstance(result.masked_text, str)


# ---------------------------------------------------------------------------
# AC16 — T026 [DbC]
# ---------------------------------------------------------------------------


def test_allow_list_over_1000_rejected() -> None:
    """T026 [DbC] — AC16: allow_list with more than 1000 items raises PIIError.

    Note: ADR-0008 normalises the cap to 1000 items (not 50 as in spec AC16 text).
    This test follows ADR-0008 (the normative cross-service policy).
    """
    from security import PIIError, pii_mask

    oversized_allow_list = ["item"] * 1001

    with pytest.raises(PIIError) as exc_info:
        pii_mask("some text", language="pt", allow_list=oversized_allow_list)

    err = exc_info.value
    assert err.code == "E_PII_ALLOW_LIST_SIZE"
    assert err.context is not None
    assert err.context["items_received"] == 1001


def test_allow_list_at_1000_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """allow_list with exactly 1000 items must NOT raise an error.

    The pool is mocked so the test does not require spaCy model installation.
    """
    from security import MaskedResult, pii_mask
    import security.guard as guard_module

    allow_list_at_cap = ["item"] * 1000
    _mock_result = MaskedResult(masked_text="some text", entities=[])

    class _FakeAsyncResult:
        def get(self, timeout: float) -> MaskedResult:  # noqa: ARG002
            return _mock_result

    class _FakePool:
        def apply_async(self, func: object, args: object) -> _FakeAsyncResult:  # noqa: ARG002
            return _FakeAsyncResult()

    monkeypatch.setattr(guard_module, "_get_pool", lambda: _FakePool())

    result = pii_mask("some text", language="pt", allow_list=allow_list_at_cap)
    assert isinstance(result.masked_text, str)


# ---------------------------------------------------------------------------
# AC17 — T027 [DbC]
# ---------------------------------------------------------------------------


def test_pii_mask_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """T027 [DbC] — AC17: processing timeout raises PIIError(E_PII_TIMEOUT).

    The pool is replaced with a fake whose async result raises mp.TimeoutError,
    simulating a Presidio worker that exceeds the 5-second timeout.

    Post (pii_mask): raises PIIError(E_PII_TIMEOUT) if processing > 5 s.

    Implementation note: we cannot monkeypatch inside a subprocess (spawn),
    so we mock _get_pool() to return a controlled fake pool whose AsyncResult
    raises mp.TimeoutError after a short delay.  The guard module's _reset_pool()
    is also mocked to avoid side effects on the real pool between tests.
    """
    from security import PIIError, pii_mask
    import security.guard as guard_module

    class _TimeoutAsyncResult:
        def get(self, timeout: float) -> None:  # noqa: ARG002
            time.sleep(0.05)  # tiny delay so the code path is realistic
            raise mp.TimeoutError()

    class _FakePool:
        def apply_async(self, func: object, args: object) -> _TimeoutAsyncResult:  # noqa: ARG002
            return _TimeoutAsyncResult()

    monkeypatch.setattr(guard_module, "_get_pool", lambda: _FakePool())
    # Prevent _reset_pool from trying to terminate a real pool during the test
    monkeypatch.setattr(guard_module, "_reset_pool", lambda: None)

    with pytest.raises(PIIError) as exc_info:
        pii_mask("some text", language="pt")

    assert exc_info.value.code == "E_PII_TIMEOUT"
