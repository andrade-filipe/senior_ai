"""Security package — PII masking via Presidio with Brazilian custom recognizers.

Public API (ADR-0003):
    pii_mask(text, language='pt', allow_list=None) -> MaskedResult

Usage:
    from security import pii_mask, MaskedResult, PIIError

    result = pii_mask("João Silva CPF 111.444.777-35", language="pt")
    print(result.masked_text)  # "<PERSON> CPF <CPF>"
    print(result.entities)     # [EntityHit(entity_type='PERSON', ...), ...]
"""

from security.errors import PIIError
from security.guard import pii_mask
from security.models import EntityHit, MaskedResult

__all__ = [
    "EntityHit",
    "MaskedResult",
    "PIIError",
    "pii_mask",
]
