"""Brazilian PII custom recognizers for Presidio.

Exports:
    get_br_recognizers: Returns list of all BR custom recognizer instances.
"""

from security.recognizers.br_cnpj import BRCNPJRecognizer
from security.recognizers.br_cpf import BRCPFRecognizer
from security.recognizers.br_phone import BRPhoneRecognizer
from security.recognizers.br_rg import BRRGRecognizer

__all__ = [
    "BRCNPJRecognizer",
    "BRCPFRecognizer",
    "BRPhoneRecognizer",
    "BRRGRecognizer",
    "get_br_recognizers",
]


def get_br_recognizers() -> list[object]:
    """Return one instance of each Brazilian PII recognizer.

    Returns:
        List of recognizer instances ready to be added to a Presidio registry.
    """
    return [
        BRCPFRecognizer(),
        BRCNPJRecognizer(),
        BRRGRecognizer(),
        BRPhoneRecognizer(),
    ]
