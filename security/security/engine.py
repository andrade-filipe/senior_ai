"""Presidio engine initialisation with LRU-cached singletons.

This module owns the AnalyzerEngine and AnonymizerEngine instances.
Engines are created once per language and cached via functools.lru_cache
to avoid repeated spaCy model loads.

Supported languages: 'pt', 'en'.  Any other language raises PIIError(E_PII_LANGUAGE).

Model requirements:
    pt: spacy pt_core_news_lg  (download: uv run python -m spacy download pt_core_news_lg)
    en: spacy en_core_web_lg   (download: uv run python -m spacy download en_core_web_lg)

If the model is missing, PIIError(E_PII_ENGINE) is raised with a corrective hint.

MAJOR-6 note — BR recognizers and language='en':
    All four BR custom recognizers (BR_CPF, BR_CNPJ, BR_RG, BR_PHONE) declare
    supported_language='pt' via their PatternRecognizer __init__.  They are
    registered in the engine's RecognizerRegistry for BOTH language builds
    (loop in get_analyzer), but Presidio will only invoke them when the analysis
    language matches their supported_language.  Therefore BR_* entities are NOT
    detected when language='en'.  This is intentional — Brazilian documents are
    submitted as PT-BR; English analysis is used for English-language content
    where Brazilian document numbers are not expected.  The spec does not require
    BR_* detection in English mode.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

from security.errors import PIIError
from security.recognizers import get_br_recognizers

_LOGGER = logging.getLogger(__name__)

_SUPPORTED_LANGUAGES = frozenset({"pt", "en"})

# spaCy model names keyed by language code
_SPACY_MODELS: dict[str, str] = {
    "pt": "pt_core_news_lg",
    "en": "en_core_web_lg",
}


def validate_language(language: str) -> None:
    """Raise PIIError(E_PII_LANGUAGE) if language is not in {'pt', 'en'}.

    Pre:
        language is a non-empty string.

    Raises:
        PIIError: code='E_PII_LANGUAGE' when language is unsupported.
    """
    if language not in _SUPPORTED_LANGUAGES:
        raise PIIError(
            code="E_PII_LANGUAGE",
            message=f"Idioma '{language}' não suportado",
            hint="Use 'pt' ou 'en'",
            context={"language": language, "supported": sorted(_SUPPORTED_LANGUAGES)},
        )


@lru_cache(maxsize=2)
def get_analyzer(language: str) -> AnalyzerEngine:
    """Return (or create) the cached AnalyzerEngine for the given language.

    The engine is built with a RecognizerRegistry that includes all BR custom
    recognizers plus Presidio's default recognizers for the specified language.

    Args:
        language: ISO 639-1 language code ('pt' or 'en').

    Returns:
        Cached AnalyzerEngine instance.

    Raises:
        PIIError: code='E_PII_ENGINE' if spaCy model load fails.
        PIIError: code='E_PII_LANGUAGE' if language is unsupported (via validate_language).

    Post:
        Returned engine has all BR custom recognizers registered.
    """
    validate_language(language)
    try:
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": _SPACY_MODELS[language]}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()

        registry = RecognizerRegistry(supported_languages=[language])
        registry.load_predefined_recognizers(languages=[language])
        for recognizer in get_br_recognizers():
            registry.add_recognizer(recognizer)  # type: ignore[arg-type]
        engine = AnalyzerEngine(
            registry=registry,
            nlp_engine=nlp_engine,
            supported_languages=[language],
        )
        _LOGGER.info(
            "Presidio AnalyzerEngine initialised",
            extra={"language": language, "recognizer_count": len(list(registry.recognizers))},
        )
        return engine
    except PIIError:
        raise
    except Exception as exc:
        model_name = _SPACY_MODELS.get(language, "unknown")
        raise PIIError(
            code="E_PII_ENGINE",
            message="Motor PII não inicializou",
            hint=(
                f"Verifique dependências: "
                f"uv run python -m spacy download {model_name}"
            ),
            context={"language": language, "cause": str(exc)},
        ) from exc


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    """Return (or create) the cached AnonymizerEngine.

    Returns:
        Cached AnonymizerEngine instance.

    Raises:
        PIIError: code='E_PII_ENGINE' if AnonymizerEngine fails to initialise.
    """
    try:
        return AnonymizerEngine()  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise PIIError(
            code="E_PII_ENGINE",
            message="Motor PII não inicializou (anonymizer)",
            hint="Verifique dependências de security/",
            context={"cause": str(exc)},
        ) from exc
