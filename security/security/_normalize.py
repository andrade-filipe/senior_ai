"""Shared normalisation utilities for BR document recognizers.

Extracted to avoid duplicating punctuation-stripping logic across
br_cpf.py and br_cnpj.py (T050 — refactor).
"""

from __future__ import annotations

import re


def strip_punctuation(value: str) -> str:
    """Remove all non-digit characters from a document number string.

    Used before passing CPF/CNPJ strings to pycpfcnpj validators, which
    require digit-only input.

    Args:
        value: Raw document string, e.g. '111.444.777-35' or '111.444.777-35'.

    Returns:
        String containing only the ASCII digit characters from ``value``.

    Post:
        Return value matches r'^\\d*$'.
    """
    return re.sub(r"\D", "", value)
