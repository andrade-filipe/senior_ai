"""Shared test fixtures for the security package.

IMPORTANT: All CPF, CNPJ values used here are SYNTHETIC (fake).

C4 validation — all numeric fixtures verified with pycpfcnpj:
    >>> from pycpfcnpj import cpf, cnpj
    >>> cpf.validate("11144477735")   # 111.444.777-35 stripped
    True
    >>> cpf.validate("00000000000")   # 000.000.000-00 stripped
    False
    >>> cnpj.validate("11222333000181")  # 11.222.333/0001-81 stripped
    True
    >>> cnpj.validate("00000000000000")  # 00.000.000/0000-00 stripped
    False

    CPF  111.444.777-35  — mathematically valid (checksum passes), not a real person.
    CPF  000.000.000-00  — structurally plausible but checksum FAILS (all zeros).
    CNPJ 11.222.333/0001-81 — mathematically valid (checksum passes), not a real company.
    CNPJ 00.000.000/0000-00 — structurally plausible but checksum FAILS.
    RG   12.345.678-9     — regex match only (no checksum); synthetic.
    Phone (11) 98765-4321 — fictional number.

None of these map to living individuals or registered entities.

Markers:
    requires_spacy: Tests that need pt_core_news_lg installed.
                    Skip with: pytest -m "not requires_spacy"
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# MAJOR-3 fix: clear lru_cache and reset multiprocessing pool between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_engine_caches() -> "pytest.Generator[None, None, None]":  # type: ignore[type-arg]
    """Autouse fixture: clear Presidio engine lru_cache before and after each test.

    Without this fixture, lru_cache singletons from one test bleed into the next,
    making monkeypatches applied to engine.get_analyzer invisible after the cache
    is populated.

    Note on pool lifecycle: the multiprocessing pool is NOT reset between tests.
    Resetting the pool triggers a new worker process spawn + spaCy model reload
    (cold start ~5-15 s), which would make the test suite prohibitively slow.
    The pool is only reset when a test explicitly needs to (e.g., timeout tests
    that monkeypatch _get_pool), and those tests handle their own cleanup via
    pytest monkeypatch teardown.
    """
    from security.engine import get_analyzer, get_anonymizer

    get_analyzer.cache_clear()
    get_anonymizer.cache_clear()
    yield
    get_analyzer.cache_clear()
    get_anonymizer.cache_clear()


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "requires_spacy: mark test as requiring a spaCy model (pt_core_news_lg or en_core_web_lg)",
    )


@pytest.fixture()
def valid_cpf() -> str:
    """Mathematically valid synthetic CPF (checksum passes)."""
    return "111.444.777-35"


@pytest.fixture()
def invalid_cpf() -> str:
    """CPF that matches the regex but fails checksum validation (all zeros)."""
    return "000.000.000-00"


@pytest.fixture()
def valid_cnpj() -> str:
    """Mathematically valid synthetic CNPJ (checksum passes)."""
    return "11.222.333/0001-81"


@pytest.fixture()
def invalid_cnpj() -> str:
    """CNPJ that matches the regex but fails checksum validation (all zeros)."""
    return "00.000.000/0000-00"


@pytest.fixture()
def valid_rg() -> str:
    """Synthetic RG in SP format (regex match; no checksum)."""
    return "12.345.678-9"


@pytest.fixture()
def valid_phone() -> str:
    """Synthetic BR phone number in standard format."""
    return "(11) 98765-4321"


@pytest.fixture()
def valid_phone_raw() -> str:
    """Synthetic BR phone number without formatting."""
    return "11 987654321"


@pytest.fixture()
def sample_text_pt(valid_cpf: str, valid_phone: str) -> str:
    """Realistic PT-BR medical order text with multiple PII types.

    Includes: PERSON name, valid CPF, valid phone, e-mail, clinical date.
    Does NOT contain a real person's data — all values are synthetic.
    """
    return (
        f"Paciente: João Silva\n"
        f"CPF: {valid_cpf}\n"
        f"Telefone: {valid_phone}\n"
        f"Email: joao.silva@example.com\n"
        f"Data: 01/05/2026\n"
        f"Exame: hemograma completo\n"
    )
