"""Tests for the recognizers package registry — get_br_recognizers().

C4 programmatic validation: the CPF/CNPJ fixture values used throughout the
test suite are explicitly verified against pycpfcnpj to guard against
"valid-looking regex match but invalid checksum" false-positives in tests.
"""

from __future__ import annotations


def test_get_br_recognizers_returns_four_recognizers() -> None:
    """get_br_recognizers returns exactly 4 BR custom recognizer instances."""
    from security.recognizers import (
        BRCNPJRecognizer,
        BRCPFRecognizer,
        BRPhoneRecognizer,
        BRRGRecognizer,
        get_br_recognizers,
    )

    recognizers = get_br_recognizers()

    assert len(recognizers) == 4
    types = {type(r) for r in recognizers}
    assert BRCPFRecognizer in types
    assert BRCNPJRecognizer in types
    assert BRRGRecognizer in types
    assert BRPhoneRecognizer in types


def test_each_recognizer_has_correct_entity_type() -> None:
    """Each BR recognizer reports the correct supported_entity."""
    from security.recognizers import (
        BRCNPJRecognizer,
        BRCPFRecognizer,
        BRPhoneRecognizer,
        BRRGRecognizer,
    )

    assert BRCPFRecognizer().supported_entities == ["BR_CPF"]
    assert BRCNPJRecognizer().supported_entities == ["BR_CNPJ"]
    assert BRRGRecognizer().supported_entities == ["BR_RG"]
    assert BRPhoneRecognizer().supported_entities == ["BR_PHONE"]


def test_normalize_strip_punctuation() -> None:
    """strip_punctuation removes all non-digit characters."""
    from security._normalize import strip_punctuation

    assert strip_punctuation("111.444.777-35") == "11144477735"
    assert strip_punctuation("11.222.333/0001-81") == "11222333000181"
    assert strip_punctuation("12345") == "12345"
    assert strip_punctuation("abc") == ""
    assert strip_punctuation("") == ""


def test_conftest_cpf_fixtures_pass_pycpfcnpj_validation() -> None:
    """C4 — verify that fixture CPF '111.444.777-35' passes pycpfcnpj checksum.

    This test guards against the scenario where a test fixture is "valid in regex"
    but actually fails the mathematical checksum, producing a false-positive in AC5
    (score >= 0.85) tests.
    """
    import re

    import pycpfcnpj.cpf as cpf_val

    valid_cpf_formatted = "111.444.777-35"
    invalid_cpf_formatted = "000.000.000-00"

    valid_digits = re.sub(r"\D", "", valid_cpf_formatted)
    invalid_digits = re.sub(r"\D", "", invalid_cpf_formatted)

    assert cpf_val.validate(valid_digits), (
        f"Fixture CPF {valid_cpf_formatted!r} must pass pycpfcnpj checksum"
    )
    assert not cpf_val.validate(invalid_digits), (
        f"Fixture CPF {invalid_cpf_formatted!r} must FAIL pycpfcnpj checksum"
    )


def test_conftest_cnpj_fixtures_pass_pycpfcnpj_validation() -> None:
    """C4 — verify that fixture CNPJ '11.222.333/0001-81' passes pycpfcnpj checksum.

    Same rationale as the CPF fixture test above — prevents false-positives in
    AC7 tests that rely on score >= 0.85 being awarded only for valid CNPJs.
    """
    import re

    import pycpfcnpj.cnpj as cnpj_val

    valid_cnpj_formatted = "11.222.333/0001-81"
    invalid_cnpj_formatted = "00.000.000/0000-00"

    valid_digits = re.sub(r"\D", "", valid_cnpj_formatted)
    invalid_digits = re.sub(r"\D", "", invalid_cnpj_formatted)

    assert cnpj_val.validate(valid_digits), (
        f"Fixture CNPJ {valid_cnpj_formatted!r} must pass pycpfcnpj checksum"
    )
    assert not cnpj_val.validate(invalid_digits), (
        f"Fixture CNPJ {invalid_cnpj_formatted!r} must FAIL pycpfcnpj checksum"
    )
