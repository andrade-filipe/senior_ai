"""Tests for data models (EntityHit, MaskedResult, sha256_prefix).

Ensures the Pydantic validators enforce all invariants defined in plan.md.
"""

from __future__ import annotations

import pytest


def test_entity_hit_valid_construction() -> None:
    """EntityHit can be constructed with valid fields."""
    from security.models import EntityHit

    hit = EntityHit(
        entity_type="BR_CPF",
        start=0,
        end=14,
        score=0.85,
        sha256_prefix="a1b2c3d4",
    )
    assert hit.entity_type == "BR_CPF"
    assert hit.sha256_prefix == "a1b2c3d4"


def test_entity_hit_rejects_non_hex_sha256_prefix() -> None:
    """sha256_prefix with non-hex characters is rejected."""
    from pydantic import ValidationError

    from security.models import EntityHit

    with pytest.raises(ValidationError):
        EntityHit(
            entity_type="BR_CPF",
            start=0,
            end=5,
            score=0.85,
            sha256_prefix="ZZZZZZZZ",  # non-hex
        )


def test_entity_hit_rejects_end_before_start() -> None:
    """EntityHit rejects end <= start (zero-length or inverted span)."""
    from pydantic import ValidationError

    from security.models import EntityHit

    with pytest.raises(ValidationError):
        EntityHit(
            entity_type="BR_CPF",
            start=10,
            end=5,  # end before start
            score=0.85,
            sha256_prefix="a1b2c3d4",
        )


def test_entity_hit_rejects_wrong_sha256_length() -> None:
    """sha256_prefix must be exactly 8 characters."""
    from pydantic import ValidationError

    from security.models import EntityHit

    with pytest.raises(ValidationError):
        EntityHit(
            entity_type="BR_CPF",
            start=0,
            end=5,
            score=0.85,
            sha256_prefix="a1b2c3",  # only 6 chars
        )


def test_sha256_prefix_function_properties() -> None:
    """sha256_prefix returns 8 lowercase hex characters deterministically."""
    from security.models import sha256_prefix

    result = sha256_prefix("111.444.777-35")
    assert len(result) == 8
    assert all(c in "0123456789abcdef" for c in result)

    # Same input always gives same output (determinism)
    assert sha256_prefix("111.444.777-35") == result


def test_masked_result_entities_default_empty() -> None:
    """MaskedResult.entities defaults to an empty list."""
    from security.models import MaskedResult

    r = MaskedResult(masked_text="hello")
    assert r.entities == []


def test_masked_result_stores_entity_hits() -> None:
    """MaskedResult stores provided EntityHit objects correctly."""
    from security.models import EntityHit, MaskedResult

    hit = EntityHit(
        entity_type="PERSON",
        start=0,
        end=4,
        score=0.8,
        sha256_prefix="deadbeef",
    )
    result = MaskedResult(masked_text="<PERSON> text", entities=[hit])
    assert len(result.entities) == 1
    assert result.entities[0].entity_type == "PERSON"
