"""Core PII masking pipeline.

Public entry-point: pii_mask().

Operator mapping (docs/ARCHITECTURE.md § Lista definitiva de entidades PII):
    BR_CPF       → replace → '<CPF>'
    BR_CNPJ      → replace → '<CNPJ>'
    BR_RG        → replace → '<RG>'
    BR_PHONE     → replace → '<PHONE>'
    PHONE_NUMBER → replace → '<PHONE>'
    PERSON       → replace → '<PERSON>'
    EMAIL_ADDRESS → replace → '<EMAIL>'
    LOCATION     → replace → '<LOCATION>'
    DATE_TIME    → keep (not masked — clinical dates are relevant, AC11)

Allow-list is applied as a post-analysis filter: any Presidio result whose
matched span (case-insensitive) exactly matches an allow-list token is dropped
before anonymization (AC12).

Timeout is enforced using multiprocessing.Pool so that a hung Presidio worker
process can be hard-killed via pool.terminate() (AC17, C2).  ThreadPoolExecutor
cannot kill threads in Python; using a separate process is the only reliable
way to enforce a hard timeout on arbitrary Presidio execution.

Windows note: Python on Windows uses 'spawn' by default, so _worker_analyze
must be a top-level (module-level) picklable function and all arguments must
also be picklable.  allow_list is passed as tuple[str, ...] | None for this reason.
"""

from __future__ import annotations

import atexit
import logging
import multiprocessing as mp
import os
import re
import threading
from multiprocessing.pool import Pool
from typing import Any

from presidio_anonymizer.entities import OperatorConfig

from security.engine import validate_language
from security.errors import PIIError
from security.models import EntityHit, MaskedResult, sha256_prefix

_LOGGER = logging.getLogger(__name__)

# Hard limits (ADR-0008 + ARCHITECTURE.md § Guardrails de tamanho).
# Defaults reproduce pre-ADR-0009 behaviour; env overrides enable operational tuning
# without rebuild (ADR-0009 — spec=default, env=override for ops). Recognizer scores
# remain hardcoded calibrations (see recognizers/br_*.py) — only the aggregate
# threshold is exposed via PII_SCORE_THRESHOLD below.
_TEXT_MAX_BYTES = int(os.environ.get("PII_TEXT_MAX_BYTES", str(100 * 1024)))  # 100 KB
_ALLOW_LIST_MAX = int(os.environ.get("PII_ALLOW_LIST_MAX", "1000"))  # 1 000 items (ADR-0008; spec AC16)
_TIMEOUT_SECONDS = float(os.environ.get("PII_TIMEOUT_SECONDS", "5"))
_PII_SCORE_THRESHOLD = float(os.environ.get("PII_SCORE_THRESHOLD", "0.5"))
_DEFAULT_LANGUAGE = os.environ.get("PII_DEFAULT_LANGUAGE", "pt")

# Entities to detect (all entities in the ARCHITECTURE table except DATE_TIME)
_ENTITIES = [
    "BR_CPF",
    "BR_CNPJ",
    "BR_RG",
    "BR_PHONE",
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "DATE_TIME",
]

# Entities that are detected but NOT masked (AC11)
_KEEP_ENTITIES: frozenset[str] = frozenset({"DATE_TIME"})

# Placeholder mapping for anonymised entities
_PLACEHOLDERS: dict[str, str] = {
    "BR_CPF": "<CPF>",
    "BR_CNPJ": "<CNPJ>",
    "BR_RG": "<RG>",
    "BR_PHONE": "<PHONE>",
    "PHONE_NUMBER": "<PHONE>",
    "PERSON": "<PERSON>",
    "EMAIL_ADDRESS": "<EMAIL>",
    "LOCATION": "<LOCATION>",
}

# ---------------------------------------------------------------------------
# Worker process pool (multiprocessing — hard-kill on timeout)
# ---------------------------------------------------------------------------

_pool_lock = threading.Lock()
_pool: Pool | None = None


def _init_worker() -> None:
    """Initialise Presidio engines in the worker process (amortises cold-start)."""
    from security.engine import get_analyzer, get_anonymizer  # noqa: PLC0415

    get_analyzer("pt")
    get_anonymizer()


def _get_pool() -> Pool:
    """Return the shared worker Pool, creating it if necessary.

    Thread-safe via _pool_lock.  The pool is created lazily so that modules
    importing guard.py at import time don't immediately spawn a child process.
    """
    global _pool  # noqa: PLW0603
    with _pool_lock:
        if _pool is None:
            _pool = mp.Pool(processes=1, initializer=_init_worker)
        return _pool


def _reset_pool() -> None:
    """Terminate and discard the worker pool.

    Called on timeout (to kill a hung worker) and via atexit (graceful shutdown).
    Thread-safe via _pool_lock.
    """
    global _pool  # noqa: PLW0603
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.terminate()
                _pool.join()
            except Exception:  # noqa: BLE001
                pass
            _pool = None


# Register cleanup so the worker process is reaped when the interpreter exits.
atexit.register(_reset_pool)


# ---------------------------------------------------------------------------
# Top-level worker function — must be picklable (module-level, no lambdas)
# ---------------------------------------------------------------------------


def _worker_analyze(
    text: str,
    language: str,
    allow_list: tuple[str, ...] | None,
    correlation_id: str | None,  # noqa: ARG001 — reserved for future audit tracing
) -> MaskedResult:
    """Execute the Presidio pipeline inside the worker process.

    This function runs in the child process spawned by _get_pool().
    It must be a top-level (module-level) function and all arguments must be
    picklable (tuple instead of list for allow_list; str | None for correlation_id).

    Args:
        text: Pre-validated input text.
        language: Pre-validated language code.
        allow_list: Tuple of tokens to exclude from masking, or None.
        correlation_id: Optional trace ID for audit purposes (not yet used).

    Returns:
        MaskedResult with masked_text and entity metadata.
    """
    from security.engine import get_analyzer, get_anonymizer  # noqa: PLC0415

    analyzer = get_analyzer(language)
    anonymizer = get_anonymizer()
    return _analyze_and_anonymize(
        analyzer, anonymizer, text, language, allow_list or (), correlation_id
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pii_mask(
    text: str,
    language: str | None = None,
    allow_list: list[str] | None = None,
    correlation_id: str | None = None,
) -> MaskedResult:
    """Detect and mask PII in ``text`` using Presidio with Brazilian custom recognizers.

    This is the single public entry-point of the security module (ADR-0003).

    Pre:
        - language must be 'pt' or 'en'.  Otherwise PIIError(E_PII_LANGUAGE) is raised.
        - len(text.encode('utf-8')) <= 100 KB.  Otherwise PIIError(E_PII_TEXT_SIZE) is raised.
        - len(allow_list) <= 1000 items.  Otherwise PIIError(E_PII_ALLOW_LIST_SIZE) is raised.
        - Processing must complete within 5 seconds.  Otherwise PIIError(E_PII_TIMEOUT) is raised.

    Post:
        - masked_text contains no raw value that was detected as a PII entity.
        - Each EntityHit in entities carries only entity_type, start, end, score,
          sha256_prefix — never the raw value.
        - DATE_TIME entities are detected (present in entities list) but NOT masked
          in masked_text (AC11).

    Invariant (idempotence, AC14):
        pii_mask(pii_mask(text, language, allow_list).masked_text, language, allow_list)
            .masked_text
        == pii_mask(text, language, allow_list).masked_text

    Args:
        text: Input text to analyse and mask.
        language: ISO 639-1 code for the NLP model to use ('pt' or 'en').
        allow_list: Optional list of exact tokens (case-insensitive) that must
                    not be masked even if detected as PII.
        correlation_id: Optional trace identifier for audit logging (does not
                        affect masking output).

    Returns:
        MaskedResult with masked_text and list of EntityHit metadata.

    Raises:
        PIIError: code='E_PII_LANGUAGE' — unsupported language.
        PIIError: code='E_PII_TEXT_SIZE' — text exceeds 100 KB.
        PIIError: code='E_PII_ALLOW_LIST_SIZE' — allow_list exceeds 1 000 items.
        PIIError: code='E_PII_TIMEOUT' — processing exceeded 5 s (worker hard-killed).
        PIIError: code='E_PII_ENGINE' — Presidio/spaCy failed to initialise.
    """
    # -- Pre-conditions (border checks before touching the engine) --
    if language is None:
        language = _DEFAULT_LANGUAGE
    validate_language(language)
    _check_text_size(text)
    _check_allow_list_size(allow_list)

    allow_tuple: tuple[str, ...] | None = tuple(allow_list) if allow_list else None

    # Run masking pipeline in worker process with hard timeout.
    # On timeout: pool.terminate() kills the worker process (unlike thread cancel).
    pool = _get_pool()
    async_result = pool.apply_async(
        _worker_analyze,
        (text, language, allow_tuple, correlation_id),
    )
    try:
        result: MaskedResult = async_result.get(timeout=_TIMEOUT_SECONDS)
    except mp.TimeoutError as exc:
        _reset_pool()  # terminate the hung worker and clear the pool
        raise PIIError(
            code="E_PII_TIMEOUT",
            message=f"Processamento PII excedeu o tempo limite de {_TIMEOUT_SECONDS} s",
            hint="Divida o texto em partes menores; verifique a saúde do Presidio",
            context={"timeout_s": _TIMEOUT_SECONDS, "text_len": len(text)},
        ) from exc

    # Parent-process audit log — only metadata, never raw values (AC18, ADR-0008).
    # Logs in the worker process are not propagated to the parent; this record is
    # the authoritative audit entry visible to test caplog fixtures.
    _LOGGER.info(
        "pii.masked",
        extra={
            "language": language,
            "entity_count": len(result.entities),
            "masked_count": sum(
                1 for h in result.entities if h.entity_type not in _KEEP_ENTITIES
            ),
            "kept_count": sum(
                1 for h in result.entities if h.entity_type in _KEEP_ENTITIES
            ),
            # sha256_prefix values only — no raw strings
            "entity_hashes": [h.sha256_prefix for h in result.entities],
        },
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers — not exported
# ---------------------------------------------------------------------------


def _check_text_size(text: str) -> None:
    """Raise PIIError(E_PII_TEXT_SIZE) if text exceeds 100 KB in UTF-8.

    Pre:
        text is a str.

    Raises:
        PIIError: code='E_PII_TEXT_SIZE'.
    """
    byte_len = len(text.encode("utf-8"))
    if byte_len > _TEXT_MAX_BYTES:
        raise PIIError(
            code="E_PII_TEXT_SIZE",
            message="Texto excede 100 KB",
            hint="Divida em chunks menores ou reduza o input",
            context={"bytes_received": byte_len, "bytes_max": _TEXT_MAX_BYTES},
        )


def _check_allow_list_size(allow_list: list[str] | None) -> None:
    """Raise PIIError(E_PII_ALLOW_LIST_SIZE) if allow_list has more than 1 000 items.

    Pre:
        allow_list is None or a list of strings.

    Raises:
        PIIError: code='E_PII_ALLOW_LIST_SIZE'.
    """
    if allow_list is not None and len(allow_list) > _ALLOW_LIST_MAX:
        raise PIIError(
            code="E_PII_ALLOW_LIST_SIZE",
            message=f"allow_list excede {_ALLOW_LIST_MAX} itens",
            hint="Revise a lista — use categorias canônicas",
            context={"items_received": len(allow_list), "items_max": _ALLOW_LIST_MAX},
        )


def _analyze_and_anonymize(
    analyzer: Any,
    anonymizer: Any,
    text: str,
    language: str,
    allow_list: tuple[str, ...],
    correlation_id: str | None,  # noqa: ARG001
) -> MaskedResult:
    """Execute the Presidio analyse → filter → anonymise pipeline.

    Called from within the worker process by _worker_analyze.

    Args:
        analyzer: Presidio AnalyzerEngine instance.
        anonymizer: Presidio AnonymizerEngine instance.
        text: Pre-validated input text.
        language: Pre-validated language code.
        allow_list: Tuple of tokens to exclude from masking (case-insensitive).
        correlation_id: Reserved for future audit tracing.

    Returns:
        MaskedResult with masked_text and entity metadata.
    """
    # Analyse — returns list[RecognizerResult].
    # score_threshold=0.5 (default) drops low-confidence matches (e.g. BR_CPF with
    # invalid checksum scored 0.1 and boosted to 0.45 by Presidio's context
    # enhancer still stays below 0.5 → dropped; AC6/AC7). Tunable via
    # PII_SCORE_THRESHOLD env (ADR-0009) — individual recognizer scores remain
    # hardcoded calibrations intentionally coupled to this threshold.
    analyzer_results = analyzer.analyze(
        text=text,
        language=language,
        entities=_ENTITIES,
        score_threshold=_PII_SCORE_THRESHOLD,
    )

    # Filter out allow-listed tokens (AC12)
    allow_set = {t.lower() for t in allow_list}
    analyzer_results = [
        r
        for r in analyzer_results
        if text[r.start : r.end].lower() not in allow_set
    ]

    # Idempotence (AC14): if the input already contains our placeholders,
    # Presidio may re-detect tokens inside them (e.g. 'EMAIL' inside '<EMAIL>'
    # as PERSON).  Drop any result whose span is fully inside an existing
    # placeholder so the second pass of pii_mask produces the same output.
    analyzer_results = _drop_results_in_placeholder_spans(text, analyzer_results)

    # Separate keep-entities from mask-entities (AC11: DATE_TIME is kept)
    results_to_mask = [r for r in analyzer_results if r.entity_type not in _KEEP_ENTITIES]
    results_kept = [r for r in analyzer_results if r.entity_type in _KEEP_ENTITIES]

    # Build operator config for each entity to mask
    operators: dict[str, OperatorConfig] = _build_operators(results_to_mask)

    # Anonymise (only masking entities; kept entities pass through)
    if results_to_mask:
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results_to_mask,
            operators=operators,
        )
        masked_text = anonymized.text
    else:
        masked_text = text

    # Build EntityHit list — raw values go directly to sha256_prefix; never stored
    entity_hits = _build_entity_hits(text, analyzer_results)

    # Note: logging here runs inside the worker process and does NOT propagate
    # to the parent process logger.  The authoritative audit log entry is emitted
    # in pii_mask() (parent process) after receiving the result.
    _ = results_kept  # referenced only for the parent-side log breakdown

    return MaskedResult(masked_text=masked_text, entities=entity_hits)


_PLACEHOLDER_RE = re.compile(r"<(?:CPF|CNPJ|RG|PHONE|PERSON|EMAIL|LOCATION)>")


def _drop_results_in_placeholder_spans(
    text: str, results: list[Any]
) -> list[Any]:
    """Drop recognizer results whose span is fully inside an existing placeholder.

    Supports idempotence (AC14): when pii_mask runs on already-masked text,
    Presidio can re-detect tokens inside placeholders (e.g. the word 'EMAIL'
    inside '<EMAIL>' as PERSON).  Such spurious matches are filtered out so
    that a second pass of pii_mask produces the same output as the first.

    Args:
        text: The (possibly already-masked) input text.
        results: List of RecognizerResult from the analyzer.

    Returns:
        Filtered list of results; those fully inside any placeholder span are removed.
    """
    placeholder_spans = [m.span() for m in _PLACEHOLDER_RE.finditer(text)]
    if not placeholder_spans:
        return results
    return [
        r
        for r in results
        if not any(
            ph_start <= r.start and r.end <= ph_end
            for ph_start, ph_end in placeholder_spans
        )
    ]


def _build_operators(results: list[Any]) -> dict[str, OperatorConfig]:
    """Build a Presidio OperatorConfig dict for all entity types to mask.

    Args:
        results: Filtered list of RecognizerResult to mask.

    Returns:
        Dict mapping entity_type to OperatorConfig(replace, placeholder).
    """
    operators: dict[str, OperatorConfig] = {}
    for r in results:
        entity = r.entity_type
        if entity not in operators:
            placeholder = _PLACEHOLDERS.get(entity, f"<{entity}>")
            operators[entity] = OperatorConfig("replace", {"new_value": placeholder})
    return operators


def _build_entity_hits(text: str, results: list[Any]) -> list[EntityHit]:
    """Convert Presidio RecognizerResult list to EntityHit list.

    The raw matched value is hashed immediately and never stored.

    Args:
        text: Original (unmasked) text.
        results: List of RecognizerResult from the analyzer.

    Returns:
        List of EntityHit with sha256_prefix computed from each raw match.

    Post:
        No raw PII value is retained after this function returns.
    """
    hits: list[EntityHit] = []
    for r in results:
        raw_value = text[r.start : r.end]
        prefix = sha256_prefix(raw_value)
        # raw_value is intentionally NOT stored — only the prefix passes forward
        hits.append(
            EntityHit(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=float(r.score),
                sha256_prefix=prefix,
            )
        )
    return hits


