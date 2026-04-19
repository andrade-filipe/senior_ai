"""Shared pytest fixtures for RAG MCP tests."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest


@pytest.fixture
def tmp_catalog_csv(tmp_path: Path) -> Path:
    """Create a minimal valid catalog CSV with 5 rows for unit tests.

    Returns:
        Path to the temporary CSV file.
    """
    csv_path = tmp_path / "test_exams.csv"
    rows = [
        {"name": "Hemograma Completo", "code": "HMG-001", "category": "hematologia", "aliases": "Hemograma|HMC"},
        {"name": "Glicemia de Jejum", "code": "GLI-001", "category": "bioquimica", "aliases": "Glicemia"},
        {"name": "Colesterol Total", "code": "COL-001", "category": "lipidios", "aliases": "CT"},
        {"name": "TSH", "code": "TSH-001", "category": "hormonios", "aliases": "Tireotropina"},
        {"name": "Creatinina", "code": "CRE-001", "category": "bioquimica", "aliases": "Creatinina Sérica"},
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "code", "category", "aliases"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def real_catalog_path() -> Path:
    """Return path to the real exams.csv catalog."""
    return Path(__file__).parent.parent / "rag_mcp" / "data" / "exams.csv"


@pytest.fixture
def duplicate_code_csv(tmp_path: Path) -> Path:
    """Create a CSV with a duplicate code for AC14 tests."""
    csv_path = tmp_path / "dup_exams.csv"
    rows = [
        {"name": "Hemograma Completo", "code": "HMG-001", "category": "hematologia", "aliases": ""},
        {"name": "Hemograma Simplificado", "code": "HMG-001", "category": "hematologia", "aliases": ""},  # duplicate
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "code", "category", "aliases"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def invalid_header_csv(tmp_path: Path) -> Path:
    """Create a CSV with invalid header for error tests."""
    csv_path = tmp_path / "bad_header.csv"
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("nome,codigo,categoria,apelidos\n")
        fh.write("Hemograma,HMG-001,hematologia,HMC\n")
    return csv_path


@pytest.fixture
def missing_file_path(tmp_path: Path) -> Path:
    """Return a path to a non-existent file."""
    return tmp_path / "does_not_exist.csv"
