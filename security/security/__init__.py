"""Security package — PII masking via Presidio with Brazilian custom recognizers.

Public API (ADR-0003):
    pii_mask(text, language='pt', allow_list=None) -> MaskedResult
    make_pii_callback(allow_list=None) -> Callable  — ADK before_model_callback factory

Usage:
    from security import pii_mask, make_pii_callback, MaskedResult, PIIError

    result = pii_mask("João Silva CPF 111.444.777-35", language="pt")
    print(result.masked_text)  # "<PERSON> CPF <CPF>"
    print(result.entities)     # [EntityHit(entity_type='PERSON', ...), ...]

    # ADK agent integration (ADR-0003 Layer 2):
    cb = make_pii_callback(allow_list=["HospitalXYZ"])
    agent = LlmAgent(..., before_model_callback=cb)
"""

from security.callback import make_pii_callback
from security.errors import PIIError
from security.guard import pii_mask
from security.models import EntityHit, MaskedResult

__all__ = [
    "EntityHit",
    "MaskedResult",
    "PIIError",
    "make_pii_callback",
    "pii_mask",
]
