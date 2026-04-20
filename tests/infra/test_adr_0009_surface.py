"""Guard: ADR-0009 HARDCODED surface — calibrations and contracts must NOT be env-backed.

ADR-0009 classifies 17 parameters as permanently hardcoded because they are
either architectural contracts (API schema max_length) or algorithm calibrations
(Presidio recognizer scores) that are deliberately coupled to other constants.
Env-ifying them would silently open mis-configuration paths.

This test suite asserts that each of those items is still a direct literal
assignment in the source code, NOT an os.environ.get(...) call.

If a test here fails, do NOT change this test — revert the change that moved
a HARDCODED parameter to env instead.

Run:
    cd <repo-root> && uv run pytest tests/infra/test_adr_0009_surface.py -v
"""

from __future__ import annotations

import pathlib

# ---------------------------------------------------------------------------
# Repository root anchor
# ---------------------------------------------------------------------------

REPO = pathlib.Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _read(relative: str) -> str:
    path = REPO / relative
    assert path.exists(), (
        f"[ADR-0009 HARDCODED guard] Expected source file not found: {path}. "
        "If the file was moved, update this guard."
    )
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Family 1: Presidio recognizer calibration scores
#
# These scores are coupled to PII_SCORE_THRESHOLD (env-backed, default 0.5).
# Example: invalid CPF yields 0.1; even with Presidio's +0.35 context boost
# the result is 0.45 < 0.5 threshold — intentional design.
# Env-ifying one score without recalibrating the threshold breaks this invariant.
# ---------------------------------------------------------------------------


def test_presidio_cpf_scores_remain_hardcoded() -> None:
    """[ADR-0009 HARDCODED] br_cpf.py: _SCORE_VALID=0.85 and _SCORE_INVALID=0.1 must be literals."""
    content = _read("security/security/recognizers/br_cpf.py")

    assert "_SCORE_VALID = 0.85" in content or "_SCORE_VALID: float = 0.85" in content, (
        "[ADR-0009 HARDCODED] br_cpf.py _SCORE_VALID must remain 0.85 literal — "
        "recognizer calibrations are coupled to PII_SCORE_THRESHOLD and must NOT be "
        "env-ified. See ADR-0009 § HARDCODED table."
    )
    assert "_SCORE_INVALID = 0.1" in content or "_SCORE_INVALID: float = 0.1" in content, (
        "[ADR-0009 HARDCODED] br_cpf.py _SCORE_INVALID must remain 0.1 literal — "
        "same coupling reason. If invalid CPF score is raised above 0.15, an invalid CPF "
        "with context boost (0.1+0.35=0.45) would still be below threshold, but the "
        "semantic guarantee would be fragile."
    )
    # Must NOT be driven from os.environ
    assert "os.environ" not in content.split("_SCORE_VALID")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_VALID in br_cpf.py must not use os.environ.get(...)."
    )
    assert "os.environ" not in content.split("_SCORE_INVALID")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_INVALID in br_cpf.py must not use os.environ.get(...)."
    )


def test_presidio_cnpj_scores_remain_hardcoded() -> None:
    """[ADR-0009 HARDCODED] br_cnpj.py: _SCORE_VALID=0.85 and _SCORE_INVALID=0.1 must be literals."""
    content = _read("security/security/recognizers/br_cnpj.py")

    assert "_SCORE_VALID = 0.85" in content or "_SCORE_VALID: float = 0.85" in content, (
        "[ADR-0009 HARDCODED] br_cnpj.py _SCORE_VALID must remain 0.85 literal."
    )
    assert "_SCORE_INVALID = 0.1" in content or "_SCORE_INVALID: float = 0.1" in content, (
        "[ADR-0009 HARDCODED] br_cnpj.py _SCORE_INVALID must remain 0.1 literal."
    )
    assert "os.environ" not in content.split("_SCORE_VALID")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_VALID in br_cnpj.py must not use os.environ.get(...)."
    )
    assert "os.environ" not in content.split("_SCORE_INVALID")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_INVALID in br_cnpj.py must not use os.environ.get(...)."
    )


def test_presidio_phone_score_remains_hardcoded() -> None:
    """[ADR-0009 HARDCODED] br_phone.py: _SCORE_BASE=0.75 must be a literal."""
    content = _read("security/security/recognizers/br_phone.py")

    assert "_SCORE_BASE = 0.75" in content or "_SCORE_BASE: float = 0.75" in content, (
        "[ADR-0009 HARDCODED] br_phone.py _SCORE_BASE must remain 0.75 literal — "
        "phone numbers have no checksum; the score is fixed by design at a value "
        "higher than RG (less ambiguous) but lower than CPF/CNPJ."
    )
    assert "os.environ" not in content.split("_SCORE_BASE")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_BASE in br_phone.py must not use os.environ.get(...)."
    )


def test_presidio_rg_score_remains_hardcoded() -> None:
    """[ADR-0009 HARDCODED] br_rg.py: _SCORE_BASE=0.5 must be a literal."""
    content = _read("security/security/recognizers/br_rg.py")

    assert "_SCORE_BASE = 0.5" in content or "_SCORE_BASE: float = 0.5" in content, (
        "[ADR-0009 HARDCODED] br_rg.py _SCORE_BASE must remain 0.5 literal — "
        "RG has high ambiguity (no checksum, format varies by state); the low score "
        "ensures it is only masked when strong context words are present."
    )
    assert "os.environ" not in content.split("_SCORE_BASE")[1].split("\n")[0], (
        "[ADR-0009 HARDCODED] _SCORE_BASE in br_rg.py must not use os.environ.get(...)."
    )


# ---------------------------------------------------------------------------
# Family 2: Scheduling API public contract field lengths
#
# These are Pydantic field constraints that define the public API schema.
# Changing them is a breaking change to the API contract and requires an
# API version bump, not an env tweak.
# ---------------------------------------------------------------------------


def test_scheduling_api_contract_lengths_remain_hardcoded() -> None:
    """[ADR-0009 HARDCODED] scheduling_api/models.py: max_length values are API contracts.

    patient_ref max_length=64, exams list max_length=20, notes max_length=500
    must remain literal integers — changing them is a breaking API change.
    """
    content = _read("scheduling_api/scheduling_api/models.py")

    assert "max_length=64" in content, (
        "[ADR-0009 HARDCODED] models.py PatientRef max_length=64 must remain a literal. "
        "This is an API contract: changing it requires a version bump, not an env tweak."
    )
    assert "max_length=20" in content, (
        "[ADR-0009 HARDCODED] models.py exams list max_length=20 must remain a literal. "
        "Same API contract reason."
    )
    assert "max_length=500" in content, (
        "[ADR-0009 HARDCODED] models.py notes max_length=500 must remain a literal. "
        "Same API contract reason."
    )

    # None of these should be driven from os.environ
    # (a simple check: os.environ should not appear near max_length assignments)
    max_length_lines = [
        line for line in content.splitlines() if "max_length" in line
    ]
    for line in max_length_lines:
        assert "os.environ" not in line, (
            f"[ADR-0009 HARDCODED] A max_length in models.py uses os.environ: {line!r}. "
            "Revert this — max_length values are API contracts."
        )


# ---------------------------------------------------------------------------
# Family 3: Internal service identifier
#
# SERVICE = "scheduling-api" is the log field that identifies this service in
# structured logs. Changing it via env would break log aggregation queries
# without any operational benefit.
# ---------------------------------------------------------------------------


def test_scheduling_api_service_name_remains_hardcoded() -> None:
    """[ADR-0009 HARDCODED] scheduling_api/logging_.py: SERVICE = 'scheduling-api' must be literal."""
    content = _read("scheduling_api/scheduling_api/logging_.py")

    assert 'SERVICE = "scheduling-api"' in content or "SERVICE = 'scheduling-api'" in content, (
        "[ADR-0009 HARDCODED] logging_.py SERVICE must remain the literal string "
        "'scheduling-api' — it is a stable identifier in structured logs. "
        "Changing it requires coordinating log aggregation queries."
    )

    # Must not be driven from env
    service_line = next(
        (line for line in content.splitlines() if "SERVICE" in line and "scheduling-api" in line),
        None,
    )
    if service_line is not None:
        assert "os.environ" not in service_line, (
            "[ADR-0009 HARDCODED] SERVICE in logging_.py must not use os.environ.get(...)."
        )


# ---------------------------------------------------------------------------
# Family 4: Supported language set in PII engine
#
# _SUPPORTED_LANGUAGES is a set that guards which language codes are valid.
# Adding a language requires: downloading + baking a new spaCy model, updating
# tests, and verifying recognizer behaviour. This is a code change, not a
# configuration change, so it must NOT be env-backed.
# ---------------------------------------------------------------------------


def test_pii_supported_languages_remains_hardcoded() -> None:
    """[ADR-0009 HARDCODED] security/engine.py: _SUPPORTED_LANGUAGES must be a hardcoded set.

    The spaCy model dict (_SPACY_MODELS) IS env-backed (PII_SPACY_MODEL_PT/EN)
    because swapping a model variant (e.g. _sm vs _lg) is an operational concern.
    But the set of supported language CODES is a code-level contract: adding 'de'
    or 'es' requires a new spaCy model baked in the Dockerfile plus test coverage.
    """
    content = _read("security/security/engine.py")

    # _SUPPORTED_LANGUAGES must exist as a frozenset or set literal, not env-backed
    assert "_SUPPORTED_LANGUAGES" in content, (
        "[ADR-0009 HARDCODED] engine.py must define _SUPPORTED_LANGUAGES."
    )

    # Confirm 'pt' and 'en' are in the literal definition
    assert '"pt"' in content or "'pt'" in content, (
        "[ADR-0009 HARDCODED] engine.py _SUPPORTED_LANGUAGES must contain 'pt'."
    )
    assert '"en"' in content or "'en'" in content, (
        "[ADR-0009 HARDCODED] engine.py _SUPPORTED_LANGUAGES must contain 'en'."
    )

    # The _SUPPORTED_LANGUAGES assignment line must not reference os.environ
    supported_lang_lines = [
        line for line in content.splitlines() if "_SUPPORTED_LANGUAGES" in line
    ]
    for line in supported_lang_lines:
        assert "os.environ" not in line, (
            f"[ADR-0009 HARDCODED] _SUPPORTED_LANGUAGES line uses os.environ: {line!r}. "
            "This must remain a hardcoded set — adding a language requires code changes."
        )
