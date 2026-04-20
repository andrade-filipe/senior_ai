"""RED tests for ocr_mcp.fixtures — T012 [DbC].

These tests MUST FAIL until fixtures.lookup() is refactored to return
`list[str] | None` (currently returns `list[str]`, using `[]` for misses).

The existing tests in ocr_mcp/tests/test_fixtures.py assert `result == []`
on miss — those tests will also fail after the GREEN refactor since the new
contract is `None` on miss (AC10). This is intentional: the old `== []`
assertions are themselves broken by the new contract. See spec 0011 AC10 and
plan.md "Breaking change interno". The old tests are left as-is; they serve
as additional RED evidence of the signature change.

Covers:
    T012 [P] [DbC] — AC1, AC10:
        (a) unknown base64 → lookup returns None (not []).
        (b) known fixture hash → lookup returns list[str] equal to _SAMPLE_EXAMS.
        (c) mutating the returned list does not affect FIXTURES[hash] (copy semantics).
"""

from __future__ import annotations

import base64
import os
import hashlib

import pytest

from ocr_mcp import fixtures as fix_module
from ocr_mcp.fixtures import (
    FIXTURES,
    _SAMPLE_EXAMS,
    _ensure_fixture_registered,
    lookup,
)


class TestLookupReturnNoneOnMissAndCopyOnHit:
    """T012 [P] [DbC] — AC1, AC10: miss → None; hit → copy of canonical list."""

    def test_lookup_returns_none_on_miss(self) -> None:
        """T012 (a): unknown hash → lookup returns None, not [].

        Pre:  image_base64 is valid base64 whose decoded bytes are NOT in FIXTURES.
        Post: returns None (new contract AC10).
        DbC:  fixtures.lookup Post — miss → None.
        AC10.
        """
        # Generate bytes that will definitely not be in FIXTURES.
        random_bytes = os.urandom(64)
        unknown_b64 = base64.b64encode(random_bytes).decode()

        result = lookup(unknown_b64)

        # New contract: None on miss — this FAILS against current [] implementation.
        assert result is None, (
            f"lookup() must return None on miss (AC10), but got: {result!r}"
        )

    def test_lookup_returns_list_on_known_hash(self) -> None:
        """T012 (b): known fixture hash → lookup returns list equal to _SAMPLE_EXAMS.

        Pre:  A synthetic hash is registered directly in FIXTURES with _SAMPLE_EXAMS.
        Post: lookup() returns a list equal to _SAMPLE_EXAMS (new contract).
        DbC:  fixtures.lookup Post — hit → canonical list.
        AC1.

        Note: we register our own synthetic bytes to avoid FIXTURES state pollution
        from other tests that may have written a different value for the PNG hash.
        """
        synthetic_bytes = b"T012_known_hash_sentinel_for_sample_exams" * 8
        synthetic_b64 = base64.b64encode(synthetic_bytes).decode()
        synthetic_hash = hashlib.sha256(synthetic_bytes).hexdigest()

        # Register the canonical exam list under this synthetic hash.
        FIXTURES[synthetic_hash] = list(_SAMPLE_EXAMS)

        result = lookup(synthetic_b64)

        assert result is not None, "lookup() must return list (not None) on hit"
        assert isinstance(result, list), "hit result must be a list"
        assert result == list(_SAMPLE_EXAMS), (
            f"hit result must equal _SAMPLE_EXAMS; got {result}"
        )

    def test_mutating_return_does_not_affect_fixtures(self) -> None:
        """T012 (c): returned list is a copy — mutation must not leak into FIXTURES.

        Pre:  A known hash is registered in FIXTURES.
        Post: Mutating the return value of lookup() does not modify FIXTURES[hash].
        DbC:  fixtures.lookup Post — returns copy, not reference.
        AC1.
        """
        # Register a custom entry directly.
        dummy_bytes = b"T012_copy_semantics_test_sentinel" * 4
        dummy_b64 = base64.b64encode(dummy_bytes).decode()
        dummy_hash = hashlib.sha256(dummy_bytes).hexdigest()
        original_list = ["Exame Alpha", "Exame Beta"]
        FIXTURES[dummy_hash] = original_list[:]  # store a copy in FIXTURES

        result = lookup(dummy_b64)

        # Precondition: result must not be None for this hit (new contract).
        assert result is not None, (
            "lookup() returned None for a registered hash; contract miss-hit"
        )

        # Mutate the returned list.
        result.append("Exame Gamma")

        # FIXTURES must be unaffected.
        assert FIXTURES[dummy_hash] == original_list, (
            "Mutating the returned list must not affect FIXTURES[hash]"
        )
