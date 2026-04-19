"""Brazilian CNPJ recognizer for Presidio.

Strategy: regex pattern match followed by checksum validation via pycpfcnpj.
Score assignment:
    - 0.1 if regex matches but checksum is invalid.
    - 0.85 if regex matches AND checksum is valid (AC7).
    - Presidio's LemmaContextAwareEnhancer adds +0.35 when context words
      ('cnpj', 'razão social', ...) are near the match.

The invalid-checksum score is intentionally low (0.1) so that even after
the +0.35 context boost the result stays below the 0.5 masking threshold
enforced by guard.py via score_threshold.

Reference: https://www.gov.br/receitafederal/pt-br/assuntos/cadastros/cnpj
           https://github.com/matheuscas/pycpfcnpj
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from security._normalize import strip_punctuation

try:
    import pycpfcnpj.cnpj as cnpj_validator
except ImportError:
    cnpj_validator = None

# Accepts: 00.000.000/0000-00 or 00000000000000 (with or without punctuation)
_CNPJ_PATTERN = r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"

_CNPJ_CONTEXT = [
    "cnpj",
    "cadastro nacional da pessoa jurídica",
    "cadastro nacional de pessoa jurídica",
    "c.n.p.j",
    "nr cnpj",
    "nro cnpj",
    "número cnpj",
    "empresa",
    "razão social",
]

_SCORE_VALID = 0.85
_SCORE_INVALID = 0.1


class BRCNPJRecognizer(PatternRecognizer):
    """Presidio PatternRecognizer for Brazilian CNPJ numbers.

    Combines regex detection with checksum validation via pycpfcnpj so that
    structurally valid but mathematically invalid CNPJs receive a low score.

    Post:
        Entities with a valid checksum get score == 0.85.
        Entities with an invalid checksum get score == 0.1 (stays below the
        0.5 masking threshold even after Presidio's +0.35 context boost).
    """

    def __init__(self) -> None:
        patterns = [Pattern(name="BR_CNPJ", regex=_CNPJ_PATTERN, score=_SCORE_INVALID)]
        super().__init__(
            supported_entity="BR_CNPJ",
            patterns=patterns,
            context=_CNPJ_CONTEXT,
            supported_language="pt",
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
        regex_flags: int | None = None,
    ) -> list[RecognizerResult]:
        """Run regex match and apply checksum validation to each hit.

        Args:
            text: Input text to analyse.
            entities: List of entity types requested by the caller.
            nlp_artifacts: NLP pipeline artefacts (unused by pattern recognizers).
            regex_flags: Optional regex flags passed to the parent class.

        Returns:
            List of RecognizerResult; score reflects checksum validity.
        """
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        for result in results:
            # In-place mutation preserves analysis_explanation set by the parent;
            # the Presidio context_aware_enhancer crashes on results whose
            # analysis_explanation is None (AttributeError on set_supportive_context_word).
            raw = text[result.start : result.end]
            digits = strip_punctuation(raw)
            result.score = _score_cnpj(digits)
        return results


def _score_cnpj(digits: str) -> float:
    """Return the confidence score for a CNPJ given its digit string.

    Args:
        digits: String containing only the 14 CNPJ digits (no punctuation).

    Returns:
        0.85 if the checksum is valid, 0.1 otherwise.
    """
    if cnpj_validator is None:
        return _SCORE_INVALID
    if cnpj_validator.validate(digits):
        return _SCORE_VALID
    return _SCORE_INVALID
