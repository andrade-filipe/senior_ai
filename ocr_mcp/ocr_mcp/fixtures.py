"""Deterministic OCR mock: SHA-256(decoded image) → canned exam name list.

The FIXTURES dict maps hex-encoded SHA-256 digests to pre-determined lists of
exam names.  This satisfies R11 (mock deterministic OCR) and AC2 (same hash →
same list).  Any unknown hash returns an empty list (AC3).

The entry for SAMPLE_MEDICAL_ORDER_HASH corresponds to the fixture PNG committed
at tests/fixtures/sample_medical_order.png.  The hash is computed lazily at
first use by _get_fixture_hash() so that:
  - The PNG does not need to exist at import time (tests generate it on-demand).
  - The FIXTURES dict always has the correct hash for the committed file.

That PNG intentionally contains a fake CPF (111.444.777-35) and a fake patient
name to exercise the PII masking pipeline (AC4, T013).

Do NOT add real patient data here. Only fixture/synthetic data for testing.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

# Path to the committed fixture PNG, relative to this file.
_FIXTURE_PNG = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_medical_order.png"

# Lazily computed hash of the fixture PNG (populated on first call to _get_fixture_hash).
_SAMPLE_HASH: str | None = None

# Canned exam list for the sample medical order fixture
_SAMPLE_EXAMS = [
    "Hemograma Completo",
    "Glicemia de Jejum",
    "Colesterol Total",
    "TSH",
    "Creatinina",
]

# ---------------------------------------------------------------------------
# Fixture registry
# Maps sha256(decoded_bytes).hexdigest() → list of canonical exam names
# ---------------------------------------------------------------------------
# NOTE: The FIXTURES dict is populated lazily via _ensure_fixture_registered().
# Call _ensure_fixture_registered() before any lookup if the PNG may have been
# generated after module import.
FIXTURES: dict[str, list[str]] = {}


def _get_fixture_hash() -> str | None:
    """Return the SHA-256 hash of the fixture PNG, or None if the file doesn't exist.

    Caches the result in module-level _SAMPLE_HASH for subsequent calls.

    Returns:
        Hex SHA-256 string of the fixture PNG, or None if file not found.
    """
    global _SAMPLE_HASH  # noqa: PLW0603
    if _SAMPLE_HASH is not None:
        return _SAMPLE_HASH
    if _FIXTURE_PNG.exists():
        with open(_FIXTURE_PNG, "rb") as fh:
            _SAMPLE_HASH = hashlib.sha256(fh.read()).hexdigest()
        return _SAMPLE_HASH
    return None


def _ensure_fixture_registered() -> None:
    """Register the fixture PNG hash in FIXTURES if the file exists.

    Called before each lookup to ensure the fixture is always registered
    even if the PNG was generated after module import.
    """
    digest = _get_fixture_hash()
    if digest is not None and digest not in FIXTURES:
        FIXTURES[digest] = list(_SAMPLE_EXAMS)


def _sha256_hex(data: bytes) -> str:
    """Return hex SHA-256 digest of data.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hex string of 64 characters.
    """
    return hashlib.sha256(data).hexdigest()


def lookup(image_base64: str) -> list[str] | None:
    """Return the canned exam list for a known image hash, or None for unknown.

    Fast-path cache for the canonical fixture. Callers (server.py) must delegate
    to real OCR when this returns None. This is a **pure lookup** — it does NOT
    call pii_mask. Callers are responsible for applying pii_mask on the result.

    Pre:
        image_base64 is a valid base64 string (RFC 4648, already decoded by caller).

    Post:
        Hit: returns a copy of the canonical exam list (mutation-safe).
        Miss: returns None (signals "delegate to real OCR").

    Invariant:
        FIXTURES is populated lazily via _ensure_fixture_registered().

    Args:
        image_base64: Base64-encoded image bytes (RFC 4648, may include padding).

    Returns:
        Copy of canonical exam list for known hashes; None for unknown hashes.

    Raises:
        base64.binascii.Error: If image_base64 is not valid base64 (caller should catch).
    """
    _ensure_fixture_registered()
    decoded = base64.b64decode(image_base64, validate=True)
    digest = _sha256_hex(decoded)
    entry = FIXTURES.get(digest)
    if entry is None:
        return None
    return list(entry)


def register_fixture(image_path: str) -> str:
    """Compute and register the hash of a PNG fixture file.

    Called once at test setup to ensure the fixture hash matches the committed PNG.
    Returns the hex digest so callers can update FIXTURES if needed.

    Args:
        image_path: Absolute path to the PNG fixture file.

    Returns:
        Hex SHA-256 digest of the file contents.
    """
    with open(image_path, "rb") as fh:
        data = fh.read()
    digest = _sha256_hex(data)
    return digest
