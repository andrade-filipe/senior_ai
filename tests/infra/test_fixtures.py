"""Fixture presence and schema validation tests (AC7, AC8).

Covers:
  AC7 — docs/fixtures/sample_medical_order.png and docs/fixtures/spec.example.json
        exist and have non-zero size.
  AC8 — spec.example.json validates successfully against transpiler.schema.AgentSpec.

No Docker required — pure filesystem + Python import tests.
"""

from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "docs" / "fixtures"

SAMPLE_IMAGE_PATH = FIXTURES_DIR / "sample_medical_order.png"
SPEC_EXAMPLE_PATH = FIXTURES_DIR / "spec.example.json"


# ---------------------------------------------------------------------------
# [AC7] Fixture files present with non-zero size
# ---------------------------------------------------------------------------


class TestFixtureFilesPresent:
    """[AC7] Required fixture files exist and are non-empty."""

    def test_sample_image_and_spec_present(self) -> None:
        """[AC7] Both fixture files exist with size > 0 bytes."""
        assert SAMPLE_IMAGE_PATH.exists(), (
            f"[AC7] sample_medical_order.png not found at {SAMPLE_IMAGE_PATH}. "
            "Create it or run the fixture generator in ocr_mcp/tests/."
        )
        assert SPEC_EXAMPLE_PATH.exists(), (
            f"[AC7] spec.example.json not found at {SPEC_EXAMPLE_PATH}. "
            "See docs/ARCHITECTURE.md § Schema Pydantic for the canonical example."
        )
        img_size = SAMPLE_IMAGE_PATH.stat().st_size
        spec_size = SPEC_EXAMPLE_PATH.stat().st_size
        assert img_size > 0, (
            f"[AC7] sample_medical_order.png is empty (0 bytes)."
        )
        assert spec_size > 0, (
            f"[AC7] spec.example.json is empty (0 bytes)."
        )

    def test_sample_image_is_png(self) -> None:
        """[AC7] sample_medical_order.png has PNG magic bytes."""
        PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
        with open(SAMPLE_IMAGE_PATH, "rb") as fh:
            header = fh.read(8)
        assert header == PNG_MAGIC, (
            f"[AC7] sample_medical_order.png does not start with PNG magic bytes. "
            f"Got: {header!r}"
        )

    def test_spec_example_is_valid_json(self) -> None:
        """[AC7] spec.example.json parses as valid JSON."""
        text = SPEC_EXAMPLE_PATH.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            pytest.fail(f"[AC7] spec.example.json is not valid JSON: {exc}")
        assert isinstance(data, dict), (
            f"[AC7] spec.example.json must be a JSON object; got {type(data)}"
        )


# ---------------------------------------------------------------------------
# [AC8] spec.example.json validates against AgentSpec schema
# ---------------------------------------------------------------------------


class TestSpecExampleSchemaValidation:
    """[AC8] spec.example.json passes transpiler.schema.AgentSpec.model_validate_json."""

    def test_spec_example_passes_transpiler_load_spec(self) -> None:
        """[AC8] load_spec(spec.example.json) returns a valid AgentSpec without error.

        This test imports transpiler.schema directly — the transpiler package
        must be installed in the active venv (add 'transpiler' to dev deps of
        the test runner if not already present).

        If transpiler is not importable, the test fails with a clear ImportError
        message pointing to the fix.
        """
        try:
            from transpiler.schema import AgentSpec
        except ImportError as exc:
            pytest.fail(
                f"[AC8] Cannot import transpiler.schema.AgentSpec: {exc}. "
                "Add 'transpiler @ file:///../transpiler' to the dev deps of "
                "the test runner venv."
            )

        text = SPEC_EXAMPLE_PATH.read_text(encoding="utf-8")
        try:
            spec = AgentSpec.model_validate_json(text)
        except Exception as exc:
            pytest.fail(
                f"[AC8] spec.example.json failed AgentSpec validation: {exc}"
            )

        # Sanity assertions on the parsed spec
        assert spec.name, "[AC8] AgentSpec.name must be non-empty."
        assert spec.model in {"gemini-2.5-flash", "gemini-2.5-flash-lite"}, (
            f"[AC8/ADR-0009] Expected model in allowlist; got {spec.model!r}."
        )
        assert len(spec.mcp_servers) >= 1, (
            "[AC8] spec.example.json must declare at least one MCP server."
        )
        assert len(spec.http_tools) >= 1, (
            "[AC8] spec.example.json must declare at least one HTTP tool."
        )
