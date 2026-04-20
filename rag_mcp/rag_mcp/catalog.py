"""Catalog loader and fuzzy search engine for RAG MCP.

Public API:
    load(path: Path) -> list[ExamEntry]
    build_choices(entries: list[ExamEntry]) -> tuple[list[str], list[ExamEntry]]
    search(query: str, choices, entries, threshold) -> ExamMatch | None

Design by Contract:
    Pre  (load):  path points to a UTF-8 CSV with header 'name,code,category,aliases'.
    Post (load):  Returns list[ExamEntry] with >= 1 entry; code is unique across all entries.
    Invariant:    code is unique — duplicate raises CatalogError(E_CATALOG_LOAD_FAILED)
                  citing the line number and value (AC14, AC20).
    Pre  (search): query is non-empty, stripped, <= 500 chars (enforced by caller).
    Post (search): Returns ExamMatch with score in [0,1] OR None below threshold.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Sequence

from rag_mcp.errors import CatalogError
from rag_mcp.models import ExamEntry, ExamMatch

# Required CSV columns in exact order (ADR-0007)
_REQUIRED_COLUMNS = ("name", "code", "category", "aliases")

# Fuzzy match threshold (ADR-0007): rapidfuzz scale 0–100
THRESHOLD = int(os.environ.get("RAG_FUZZY_THRESHOLD", "80"))


def load(path: Path) -> list[ExamEntry]:
    """Load and validate the exam catalog from a CSV file.

    Pre:
        path is an accessible UTF-8 CSV file with header 'name,code,category,aliases'.

    Post:
        Returns list[ExamEntry] with len >= 1.
        All entries have unique code values.

    Invariant:
        Duplicate code raises CatalogError citing line and value (AC14, AC20).

    Args:
        path: Filesystem path to the catalog CSV file.

    Returns:
        List of ExamEntry objects in CSV row order.

    Raises:
        CatalogError: code='E_CATALOG_LOAD_FAILED' — file missing, invalid header,
                      duplicate code, encoding error, or empty catalog.
                      Message cites line number and offending value for duplicates.
    """
    if not Path(path).exists():
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message=f"Falha ao carregar catálogo: arquivo não encontrado",
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"path": str(path)},
        )

    try:
        return _parse_csv(path)
    except CatalogError:
        raise
    except Exception as exc:
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message=f"Falha ao carregar catálogo: {exc}",
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"path": str(path)},
        ) from exc


def _parse_csv(path: Path) -> list[ExamEntry]:
    """Read CSV, validate header and content, return list of ExamEntry.

    Args:
        path: Existing CSV file path.

    Returns:
        Validated list of ExamEntry.

    Raises:
        CatalogError: On invalid header, duplicate code, or encoding error.
    """
    entries: list[ExamEntry] = []
    seen_codes: dict[str, int] = {}  # code -> line number

    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            _validate_header(reader.fieldnames, path)

            for raw_line_number, row in enumerate(reader, start=2):  # data starts at line 2
                entry = _parse_row(row, raw_line_number, seen_codes, path)
                entries.append(entry)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message=f"Falha ao carregar catálogo: erro de encoding ou CSV malformado",
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"path": str(path), "detail": str(exc)},
        ) from exc

    if not entries:
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message="Falha ao carregar catálogo: arquivo vazio ou sem linhas de dados",
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"path": str(path)},
        )

    return entries


def _validate_header(
    fieldnames: Sequence[str] | None, path: Path
) -> None:
    """Validate CSV header matches required columns in exact order.

    Args:
        fieldnames: Column names from csv.DictReader.
        path: File path for error context.

    Raises:
        CatalogError: If header is missing or does not match required columns.
    """
    if not fieldnames:
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message="Falha ao carregar catálogo: header ausente ou arquivo vazio",
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"path": str(path)},
        )
    actual = tuple(f.strip() for f in fieldnames)
    if actual != _REQUIRED_COLUMNS:
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message=(
                f"Falha ao carregar catálogo: header inválido. "
                f"Esperado {_REQUIRED_COLUMNS}, encontrado {actual}"
            ),
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"expected": list(_REQUIRED_COLUMNS), "found": list(actual)},
        )


def _parse_row(
    row: dict[str, Any],
    line_number: int,
    seen_codes: dict[str, int],
    path: Path,
) -> ExamEntry:
    """Parse a single CSV row into an ExamEntry.

    Args:
        row: Raw dict from csv.DictReader.
        line_number: 1-based line number in the file (for error messages).
        seen_codes: Accumulator tracking (code -> first seen line) for duplicate detection.
        path: File path for error context.

    Returns:
        Validated ExamEntry.

    Raises:
        CatalogError: If code is duplicated, citing line number and value (AC14).
    """
    code = (row.get("code") or "").strip()
    name = (row.get("name") or "").strip()
    category = (row.get("category") or "").strip()
    aliases_raw = (row.get("aliases") or "").strip()

    # Duplicate code check (AC14, AC20): cite line + value
    if code in seen_codes:
        first_line = seen_codes[code]
        raise CatalogError(
            code="E_CATALOG_LOAD_FAILED",
            message=(
                f"Falha ao carregar catálogo: duplicate code '{code}' at line {line_number} "
                f"(first seen at line {first_line})"
            ),
            hint="Inspecione `rag_mcp/data/exams.csv`",
            context={"duplicate_code": code, "line": line_number, "first_line": first_line},
        )
    seen_codes[code] = line_number

    aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()] if aliases_raw else []

    return ExamEntry(name=name, code=code, category=category, aliases=aliases)


def build_choices(
    entries: list[ExamEntry],
) -> tuple[list[str], dict[str, ExamEntry]]:
    """Build rapidfuzz choices from catalog entries.

    Includes both canonical names and aliases, mapping each to its parent entry.
    This allows alias-based matches to resolve to the canonical code (AC9).

    Args:
        entries: Validated catalog entries.

    Returns:
        Tuple of (choices_list, choice_to_entry_map) where:
            choices_list: All searchable strings (names + aliases).
            choice_to_entry_map: Maps each choice string to its canonical ExamEntry.
    """
    choices: list[str] = []
    mapping: dict[str, ExamEntry] = {}

    for entry in entries:
        # Add canonical name
        choices.append(entry.name)
        mapping[entry.name] = entry
        # Add each alias
        for alias in entry.aliases:
            choices.append(alias)
            mapping[alias] = entry

    return choices, mapping


def search(
    query: str,
    choices: list[str],
    mapping: dict[str, ExamEntry],
    threshold: int = THRESHOLD,
) -> ExamMatch | None:
    """Fuzzy search the catalog for the best match to query.

    Pre:
        query is non-empty after strip() and <= 500 chars (enforced by caller).
        threshold is in [0, 100].

    Post:
        Returns ExamMatch with score in [0.0, 1.0] when best score >= threshold/100.
        Returns None when no candidate reaches the threshold (AC8).
        score is derived from rapidfuzz WRatio / 100 — never outside [0.0, 1.0] (AC13).

    Args:
        query: Exam name to search for.
        choices: List of searchable strings from build_choices().
        mapping: Maps choice strings to their canonical ExamEntry.
        threshold: Minimum score (0–100 rapidfuzz scale) to consider a match.

    Returns:
        ExamMatch or None.
    """
    from rapidfuzz import fuzz, process  # noqa: PLC0415

    result = process.extractOne(
        query,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
    )
    if result is None:
        return None

    best_match_str, raw_score, _ = result
    entry = mapping[best_match_str]

    # Normalize to [0, 1] — rapidfuzz WRatio returns 0–100
    normalized_score = raw_score / 100.0
    # Clamp to [0.0, 1.0] for safety (floating point arithmetic)
    normalized_score = max(0.0, min(1.0, normalized_score))

    return ExamMatch(name=entry.name, code=entry.code, score=normalized_score)
