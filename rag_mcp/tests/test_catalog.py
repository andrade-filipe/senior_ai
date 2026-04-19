"""Tests for rag_mcp.catalog — all catalog and search ACs (T015–T019, T024–T030).

Covers:
    T015 [DbC] [AC6]:  CSV has >= 100 entries (real catalog)
    T016 [DbC] [AC7]:  Exact match returns score >= 0.95
    T017 [DbC] [AC8]:  Typo below threshold returns None
    T018 [AC9]:        Alias match resolves to canonical code
    T019 [AC10]:       list_exams(limit=5) returns exactly 5, in CSV order
    T024 [DbC] [AC13]: ExamMatch.score in [0.0, 1.0] for all matches
    T025 [DbC] [AC14]: Duplicate code raises CatalogError citing line and value
    T026 [DbC] [AC18]: Query > 500 chars → E_RAG_QUERY_TOO_LARGE
    T027 [DbC] [AC19]: Empty/whitespace query → E_RAG_QUERY_EMPTY
    T028 [AC20]:        Missing file → CatalogError(E_CATALOG_LOAD_FAILED)
    T029 [DbC] [AC21]: search_exam_code timeout → E_RAG_TIMEOUT
    T030 [DbC] [AC20]: Missing file raises CatalogError with path context
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from rag_mcp.catalog import build_choices, load, search
from rag_mcp.errors import CatalogError, RagError
from rag_mcp.models import ExamMatch, ExamSummary
from rag_mcp.server import list_exams, load_catalog, search_exam_code


# ---------------------------------------------------------------------------
# Catalog load tests
# ---------------------------------------------------------------------------


class TestCatalogLoad:
    """Tests for catalog.load() contract."""

    def test_load_valid_csv(self, tmp_catalog_csv: Path) -> None:
        """T015 partial: load() returns entries from a valid 5-row CSV."""
        entries = load(tmp_catalog_csv)
        assert len(entries) == 5
        assert entries[0].name == "Hemograma Completo"
        assert entries[0].code == "HMG-001"
        assert entries[0].aliases == ["Hemograma", "HMC"]

    def test_csv_has_100_plus_entries(self, real_catalog_path: Path) -> None:
        """T015 [DbC] [AC6]: real exams.csv has >= 100 entries."""
        entries = load(real_catalog_path)
        assert len(entries) >= 100, (
            f"Catalog has only {len(entries)} entries; >= 100 required (AC6)"
        )

    def test_real_catalog_header_valid(self, real_catalog_path: Path) -> None:
        """T015 [AC6]: real catalog loads without exception."""
        entries = load(real_catalog_path)
        assert all(e.code for e in entries)
        assert all(e.name for e in entries)

    def test_missing_file_raises_catalog_error(self, missing_file_path: Path) -> None:
        """T030 [DbC] [AC20]: missing file raises CatalogError(E_CATALOG_LOAD_FAILED)."""
        with pytest.raises(CatalogError) as exc_info:
            load(missing_file_path)

        err = exc_info.value
        assert err.code == "E_CATALOG_LOAD_FAILED"
        assert "path" in err.context or str(missing_file_path) in err.message or str(missing_file_path) in str(err.context)

    def test_invalid_header_raises_catalog_error(self, invalid_header_csv: Path) -> None:
        """T028 partial [AC20]: invalid header raises CatalogError."""
        with pytest.raises(CatalogError) as exc_info:
            load(invalid_header_csv)

        err = exc_info.value
        assert err.code == "E_CATALOG_LOAD_FAILED"

    def test_duplicate_code_rejected_with_line_ref(self, duplicate_code_csv: Path) -> None:
        """T025 [DbC] [AC14]: duplicate code raises CatalogError citing line and value."""
        with pytest.raises(CatalogError) as exc_info:
            load(duplicate_code_csv)

        err = exc_info.value
        assert err.code == "E_CATALOG_LOAD_FAILED"
        # Must cite the duplicate code value (AC14)
        assert "HMG-001" in err.message
        # Must cite the line number (AC14)
        assert any(char.isdigit() for char in err.message), (
            "Error message must contain a line number"
        )

    def test_codes_are_unique_in_real_catalog(self, real_catalog_path: Path) -> None:
        """T025 [AC14]: real catalog has unique codes (invariant)."""
        entries = load(real_catalog_path)
        codes = [e.code for e in entries]
        assert len(codes) == len(set(codes)), "Duplicate codes found in real catalog"


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestSearchExamCode:
    """Tests for search() and search_exam_code() tool."""

    def test_exact_match_returns_high_score(self, tmp_catalog_csv: Path) -> None:
        """T016 [DbC] [AC7]: exact query → ExamMatch with score >= 0.95."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        result = search("Hemograma Completo", choices, mapping)

        assert result is not None
        assert result.name == "Hemograma Completo"
        assert result.code == "HMG-001"
        assert result.score >= 0.95

    def test_typo_below_threshold_returns_none(self, tmp_catalog_csv: Path) -> None:
        """T017 [DbC] [AC8]: very different query returns None (below threshold 80)."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        # A query that is clearly different from all 5 entries
        result = search("Ressonância Magnética Crânio", choices, mapping)

        assert result is None

    def test_typo_above_threshold_returns_match(self, tmp_catalog_csv: Path) -> None:
        """T017 [DbC] [AC8]: minor typo above threshold → returns match."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        # "Hemograma Complet" is close enough to "Hemograma Completo"
        result = search("Hemograma Complet", choices, mapping)

        assert result is not None
        assert result.code == "HMG-001"

    def test_alias_match_resolves_to_canonical_code(self, tmp_catalog_csv: Path) -> None:
        """T018 [AC9]: alias 'HMC' resolves to canonical code 'HMG-001'."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        result = search("HMC", choices, mapping)

        assert result is not None
        assert result.code == "HMG-001"  # canonical code, not alias

    def test_alias_tireotropina_resolves_to_tsh(self, tmp_catalog_csv: Path) -> None:
        """T018 [AC9]: alias 'Tireotropina' resolves to TSH code."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        result = search("Tireotropina", choices, mapping)

        assert result is not None
        assert result.code == "TSH-001"

    def test_exam_match_score_in_0_1_range(self, tmp_catalog_csv: Path) -> None:
        """T024 [DbC] [AC13]: all match scores are in [0.0, 1.0]."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        queries = ["Hemograma", "Glicemia", "Colesterol", "TSH", "Creatinina"]
        for q in queries:
            result = search(q, choices, mapping)
            if result is not None:
                assert 0.0 <= result.score <= 1.0, (
                    f"score {result.score} for '{q}' is outside [0, 1]"
                )

    def test_no_match_returns_none_not_invalid_score(self, tmp_catalog_csv: Path) -> None:
        """T024 [DbC] [AC13]: no match returns None, never ExamMatch with score < 0."""
        entries = load(tmp_catalog_csv)
        choices, mapping = build_choices(entries)

        result = search("XXXXXXXXXXX", choices, mapping)

        # None is the only valid return for no-match (not ExamMatch with score < threshold)
        assert result is None


# ---------------------------------------------------------------------------
# list_exams tool tests
# ---------------------------------------------------------------------------


class TestListExams:
    """Tests for list_exams() tool."""

    @pytest.mark.asyncio
    async def test_list_exams_limit_5_ordered(self, tmp_catalog_csv: Path) -> None:
        """T019 [AC10]: list_exams(limit=5) returns exactly 5 entries in CSV order."""
        load_catalog(tmp_catalog_csv)

        result = await list_exams(limit=5)

        assert len(result) == 5
        assert result[0].name == "Hemograma Completo"
        assert result[0].code == "HMG-001"
        assert result[1].name == "Glicemia de Jejum"

    @pytest.mark.asyncio
    async def test_list_exams_returns_exam_summary(self, tmp_catalog_csv: Path) -> None:
        """T019 [AC10]: each item is an ExamSummary with name and code."""
        load_catalog(tmp_catalog_csv)

        result = await list_exams(limit=3)

        assert all(isinstance(item, ExamSummary) for item in result)
        assert all(item.name for item in result)
        assert all(item.code for item in result)

    @pytest.mark.asyncio
    async def test_list_exams_limit_exceeds_catalog(self, tmp_catalog_csv: Path) -> None:
        """T019: limit larger than catalog returns all entries."""
        load_catalog(tmp_catalog_csv)

        result = await list_exams(limit=1000)

        assert len(result) == 5  # catalog has 5 entries


# ---------------------------------------------------------------------------
# Guard tests for search_exam_code tool
# ---------------------------------------------------------------------------


class TestRagQueryGuards:
    """Tests for AC18 (too large), AC19 (empty), AC21 (timeout)."""

    @pytest.mark.asyncio
    async def test_rag_query_too_large_rejected(self, tmp_catalog_csv: Path) -> None:
        """T026 [DbC] [AC18]: query > 500 chars → ToolError(E_RAG_QUERY_TOO_LARGE)."""
        load_catalog(tmp_catalog_csv)
        oversized_query = "A" * 501

        with pytest.raises(ToolError) as exc_info:
            await search_exam_code(oversized_query)

        assert "E_RAG_QUERY_TOO_LARGE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rapidfuzz_not_called_on_too_large(self, tmp_catalog_csv: Path) -> None:
        """T026 [DbC] [AC18]: rapidfuzz is NOT called when query exceeds cap."""
        load_catalog(tmp_catalog_csv)

        with patch("rag_mcp.catalog.search") as mock_search:
            with pytest.raises(ToolError):
                await search_exam_code("A" * 501)
            mock_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_rag_empty_query_rejected(self, tmp_catalog_csv: Path) -> None:
        """T027 [DbC] [AC19]: empty string → ToolError(E_RAG_QUERY_EMPTY)."""
        load_catalog(tmp_catalog_csv)

        with pytest.raises(ToolError) as exc_info:
            await search_exam_code("")

        assert "E_RAG_QUERY_EMPTY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_whitespace_only_query_rejected(self, tmp_catalog_csv: Path) -> None:
        """T027 [DbC] [AC19]: whitespace-only string → ToolError(E_RAG_QUERY_EMPTY)."""
        load_catalog(tmp_catalog_csv)

        with pytest.raises(ToolError) as exc_info:
            await search_exam_code("   ")

        assert "E_RAG_QUERY_EMPTY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rag_search_timeout(self, tmp_catalog_csv: Path) -> None:
        """T029 [DbC] [AC21]: search timeout → ToolError(E_RAG_TIMEOUT)."""
        load_catalog(tmp_catalog_csv)

        async def slow_search(_: str) -> None:
            await asyncio.sleep(10)

        # Patch _search_async as a new async function (not side_effect, to be a coroutine)
        with patch("rag_mcp.server._search_async", new=slow_search):
            with patch("rag_mcp.server._SEARCH_TIMEOUT_S", 0.05):  # speed up for test
                with pytest.raises(ToolError) as exc_info:
                    await search_exam_code("Hemograma")

        assert "E_RAG_TIMEOUT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exactly_500_chars_is_accepted(self, tmp_catalog_csv: Path) -> None:
        """T026: exactly 500 chars is accepted (boundary condition)."""
        load_catalog(tmp_catalog_csv)
        boundary_query = "A" * 500

        # Should not raise query-too-large; may return None (no match)
        result = await search_exam_code(boundary_query)
        # result can be None (no match) — that's fine
        assert result is None or isinstance(result, ExamMatch)


# ---------------------------------------------------------------------------
# Server startup failure test
# ---------------------------------------------------------------------------


class TestCatalogLoadFailureShape:
    """T028 [AC20]: missing file causes startup failure with canonical error shape."""

    def test_catalog_load_missing_file_error(self, missing_file_path: Path) -> None:
        """T030 [DbC] [AC20]: missing path raises CatalogError with context."""
        with pytest.raises(CatalogError) as exc_info:
            load(missing_file_path)

        err = exc_info.value
        assert err.code == "E_CATALOG_LOAD_FAILED"
        assert err.message  # non-empty message
        assert err.context  # context has path info

    def test_catalog_error_to_dict_shape(self, missing_file_path: Path) -> None:
        """T028 [AC20]: CatalogError.to_dict() matches ADR-0008 shape."""
        with pytest.raises(CatalogError) as exc_info:
            load(missing_file_path)

        err = exc_info.value
        shape = err.to_dict()

        assert "code" in shape
        assert "message" in shape
        assert shape["code"] == "E_CATALOG_LOAD_FAILED"
