"""Tests ensuring generated Python files pass ast.parse.

Covers AC3 (gate ast.parse on all .py outputs) and AC5 (broken template
raises E_TRANSPILER_SYNTAX).

Run:
    uv run pytest transpiler/tests/test_ast_validation.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from transpiler import TranspilerError, load_spec, render
from transpiler import generator as gen_mod


def _spec_no_pii() -> dict[str, Any]:
    return {
        "name": "ast-test-agent",
        "description": "Agent for AST validation tests",
        "model": "gemini-2.5-flash",
        "instruction": "Test instruction.",
        "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
        "http_tools": [],
        "guardrails": {"pii": {"enabled": False, "allow_list": []}},
    }


# ---------------------------------------------------------------------------
# AC3 — All .py files in generated_agent/ pass ast.parse
# ---------------------------------------------------------------------------


def test_all_py_files_pass_ast_parse(tmp_path: Path) -> None:
    """AC3 — every .py file emitted by render passes ast.parse without SyntaxError."""
    spec = load_spec(_spec_no_pii())
    render(spec, tmp_path)

    dest = tmp_path / "generated_agent"
    py_files = list(dest.glob("*.py"))
    assert py_files, "no .py files generated"

    for py_file in py_files:
        source = py_file.read_text(encoding="utf-8")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"ast.parse failed on {py_file.name}: {exc}")


def test_all_py_files_pass_ast_parse_with_pii(tmp_path: Path) -> None:
    """AC3 (variant) — .py files pass ast.parse when pii_enabled=True."""
    spec = load_spec(
        {
            "name": "pii-agent",
            "description": "PII-enabled agent",
            "model": "gemini-2.5-flash",
            "instruction": "Guard PII.",
            "mcp_servers": [
                {"name": "ocr", "url": "http://ocr:8001/sse"},
                {"name": "rag", "url": "http://rag:8002/sse"},
            ],
            "http_tools": [
                {
                    "name": "scheduling",
                    "base_url": "http://scheduling-api:8000",
                    "openapi_url": "http://scheduling-api:8000/openapi.json",
                }
            ],
            "guardrails": {"pii": {"enabled": True, "allow_list": []}},
        }
    )
    render(spec, tmp_path)

    dest = tmp_path / "generated_agent"
    for py_file in dest.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"ast.parse failed on {py_file.name}: {exc}")


# ---------------------------------------------------------------------------
# AC5 — E_TRANSPILER_SYNTAX raised and cites filename
# ---------------------------------------------------------------------------


def test_syntax_error_cites_filename(tmp_path: Path) -> None:
    """AC5 — TranspilerError has code='E_TRANSPILER_SYNTAX' and path contains filename."""
    spec = load_spec(_spec_no_pii())

    original = gen_mod._render_template  # noqa: SLF001

    def _bad(env: Any, template_name: str, ctx: Any) -> str:
        if template_name == "agent.py.j2":
            return "class !invalid syntax"
        return original(env, template_name, ctx)

    with patch.object(gen_mod, "_render_template", side_effect=_bad):
        with pytest.raises(TranspilerError) as exc_info:
            render(spec, tmp_path)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SYNTAX"
    assert err.path is not None
    assert "agent.py" in err.path


def test_syntax_error_has_actionable_hint(tmp_path: Path) -> None:
    """AC5 — TranspilerError for syntax error includes a non-empty hint."""
    spec = load_spec(_spec_no_pii())

    original = gen_mod._render_template  # noqa: SLF001

    def _bad(env: Any, template_name: str, ctx: Any) -> str:
        if template_name == "agent.py.j2":
            return "def broken !!!"
        return original(env, template_name, ctx)

    with patch.object(gen_mod, "_render_template", side_effect=_bad):
        with pytest.raises(TranspilerError) as exc_info:
            render(spec, tmp_path)

    assert exc_info.value.hint is not None
    assert len(exc_info.value.hint) > 0
