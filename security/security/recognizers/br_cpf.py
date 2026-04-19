"""Brazilian CPF recognizer for Presidio.

Strategy: regex pattern match followed by checksum validation via pycpfcnpj.
Score assignment:
    - 0.1 if regex matches but checksum is invalid.
    - 0.85 if regex matches AND checksum is valid (AC5).
    - Presidio's LemmaContextAwareEnhancer adds +0.35 when context words
      ('cpf', 'cadastro de pessoa física', ...) are near the match.

The invalid-checksum score is intentionally low (0.1) so that even after
the +0.35 context boost the result stays below the 0.5 masking threshold
enforced by guard.py via score_threshold, guaranteeing AC6.

Reference: https://www.gov.br/receitafederal/pt-br/assuntos/cadastros/cpf
           https://github.com/matheuscas/pycpfcnpj
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from security._normalize import strip_punctuation

try:
    import pycpfcnpj.cpf as cpf_validator
except ImportError:
    cpf_validator = None

# Accepts: 000.000.000-00 or 00000000000 (with or without punctuation)
_CPF_PATTERN = r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"

# Context words in PT-BR that increase confidence when adjacent to the match
_CPF_CONTEXT = [
    "cpf",
    "cadastro de pessoa física",
    "cadastro de pessoas físicas",
    "c.p.f",
    "nr cpf",
    "nro cpf",
    "número cpf",
    "documento",
]

_SCORE_VALID = 0.85
_SCORE_INVALID = 0.1


class BRCPFRecognizer(PatternRecognizer):
    """Presidio PatternRecognizer for Brazilian CPF numbers.

    Combines regex detection with checksum validation via pycpfcnpj so that
    structurally valid but mathematically invalid CPFs receive a low score and
    are not masked (AC6).

    Post:
        Entities with a valid checksum get score == 0.85.
        Entities with an invalid checksum get score == 0.1 (below masking threshold
        even after Presidio's +0.35 context boost).

    Invariant:
        The validation_callback is executed for every regex match; raw CPF
        values are never stored or logged by this class.
    """

    def __init__(self) -> None:
        patterns = [Pattern(name="BR_CPF", regex=_CPF_PATTERN, score=_SCORE_INVALID)]
        super().__init__(
            supported_entity="BR_CPF",
            patterns=patterns,
            context=_CPF_CONTEXT,
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

        Post:
            Each result has score == 0.85 if CPF digits are valid,
            or score == 0.1 if the checksum fails.
        """
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        for result in results:
            # In-place mutation preserves analysis_explanation set by the parent;
            # the Presidio context_aware_enhancer crashes on results whose
            # analysis_explanation is None (AttributeError on set_supportive_context_word).
            raw = text[result.start : result.end]
            digits = strip_punctuation(raw)
            result.score = _score_cpf(digits)
        return results


def _score_cpf(digits: str) -> float:
    """Return the confidence score for a CPF given its digit string.

    Args:
        digits: String containing only the 11 CPF digits (no punctuation).

    Returns:
        0.85 if the checksum is valid, 0.1 otherwise.
    """
    if cpf_validator is None:
        # pycpfcnpj unavailable — fall back to regex-only score
        return _SCORE_INVALID
    if cpf_validator.validate(digits):
        return _SCORE_VALID
    return _SCORE_INVALID
