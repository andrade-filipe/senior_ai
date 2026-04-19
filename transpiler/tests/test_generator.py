"""Tests for transpiler.generator — AgentSpec → generated_agent/ package.

Each test maps to one Acceptance Criterion from
docs/specs/0002-transpiler-mvp/spec.md. Tests tagged [DbC] exercise
formal Design-by-Contract invariants documented in plan.md § Design by Contract.

Run:
    uv run pytest transpiler/tests/test_generator.py -v
"""

from __future__ import annotations

import ast
import filecmp
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from transpiler import TranspilerError, load_spec, render
from transpiler import generator as gen_mod
from transpiler.generator import _context


# ---------------------------------------------------------------------------
# AC1 — Package files exist after render
# T010 [P]
# ---------------------------------------------------------------------------


def test_generates_package_files(spec_example_dict: dict[str, Any], tmp_path: Path) -> None:
    """AC1 — generated_agent/ contains all required files after render.

    Expected files: __init__.py, agent.py, requirements.txt, Dockerfile,
    .env.example.
    """
    spec = load_spec(spec_example_dict)
    render(spec, tmp_path)

    dest = tmp_path / "generated_agent"
    assert dest.is_dir()

    required = {"__init__.py", "agent.py", "requirements.txt", "Dockerfile", ".env.example"}
    generated = {f.name for f in dest.iterdir()}
    assert required == generated


# ---------------------------------------------------------------------------
# AC2 — Determinism: two renders produce byte-for-byte identical outputs
# T011 [P] [DbC] — render.Invariant
# ---------------------------------------------------------------------------


def test_deterministic_output(spec_example_dict: dict[str, Any]) -> None:
    """AC2 [DbC render.Invariant] — two renders in distinct tmpdirs are identical.

    Renders the same spec twice into separate temp directories, then uses
    filecmp.dircmp to assert zero diff.
    """
    spec = load_spec(spec_example_dict)

    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        render(spec, Path(tmp_a))
        render(spec, Path(tmp_b))

        cmp = filecmp.dircmp(
            str(Path(tmp_a) / "generated_agent"),
            str(Path(tmp_b) / "generated_agent"),
        )
        assert cmp.diff_files == [], f"Non-deterministic output: {cmp.diff_files}"
        assert cmp.left_only == []
        assert cmp.right_only == []


# ---------------------------------------------------------------------------
# AC3 — Generated agent.py passes ast.parse
# T012 [P] [DbC] — render.Post (gate ast.parse)
# ---------------------------------------------------------------------------


def test_generated_py_is_parseable(spec_example_dict: dict[str, Any], tmp_path: Path) -> None:
    """AC3 [DbC render.Post] — agent.py produced by render passes ast.parse.

    Also checks __init__.py for syntactic validity.
    """
    spec = load_spec(spec_example_dict)
    render(spec, tmp_path)

    dest = tmp_path / "generated_agent"
    for py_file in dest.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"ast.parse failed on {py_file.name}: {exc}")


# ---------------------------------------------------------------------------
# AC5 — Broken template raises E_TRANSPILER_SYNTAX
# T014 [P]
# ---------------------------------------------------------------------------


def test_syntax_error_raised_when_template_broken(
    spec_example_dict: dict[str, Any],
    tmp_path: Path,
) -> None:
    """AC5 — when a template produces invalid Python, TranspilerError E_TRANSPILER_SYNTAX
    is raised, citing the file that failed ast.parse.
    """
    spec = load_spec(spec_example_dict)

    # Patch _render_template to return broken Python for agent.py.j2
    original = gen_mod._render_template  # noqa: SLF001

    def _broken_render(env: Any, template_name: str, ctx: Any) -> str:
        if template_name == "agent.py.j2":
            return "def broken syntax !!!\n"
        return original(env, template_name, ctx)

    with patch.object(gen_mod, "_render_template", side_effect=_broken_render):
        with pytest.raises(TranspilerError) as exc_info:
            render(spec, tmp_path)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SYNTAX"
    assert "agent.py" in (err.path or "") or "agent.py" in err.message


# ---------------------------------------------------------------------------
# AC6 — agent.py contains required ADK imports and constructs
# T015 [P]
# ---------------------------------------------------------------------------


def test_agent_py_has_mcp_toolset_import(
    spec_example_dict: dict[str, Any],
    tmp_path: Path,
) -> None:
    """AC6 — agent.py contains:
    - from google.adk.agents import LlmAgent
    - McpToolset with StreamableHTTPConnectionParams per mcp_servers entry
    - before_model_callback when guardrails.pii.enabled=True
    """
    spec = load_spec(spec_example_dict)
    render(spec, tmp_path)

    agent_py = (tmp_path / "generated_agent" / "agent.py").read_text(encoding="utf-8")

    assert "from google.adk.agents import LlmAgent" in agent_py
    assert "McpToolset" in agent_py
    assert "StreamableHTTPConnectionParams" in agent_py
    # Two MCP servers in example spec
    assert "ocr_toolset" in agent_py
    assert "rag_toolset" in agent_py
    # PII guard is enabled in example spec
    assert "before_model_callback" in agent_py


def test_agent_py_no_pii_callback_when_disabled(tmp_path: Path) -> None:
    """AC6 (complement) — no before_model_callback when pii.enabled=False."""
    spec = load_spec(
        {
            "name": "no-pii-agent",
            "description": "Agent without PII guard",
            "model": "gemini-2.5-flash",
            "instruction": "Help the user.",
            "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
            "http_tools": [],
            "guardrails": {"pii": {"enabled": False, "allow_list": []}},
        }
    )
    render(spec, tmp_path)

    agent_py = (tmp_path / "generated_agent" / "agent.py").read_text(encoding="utf-8")

    assert "before_model_callback" not in agent_py


# ---------------------------------------------------------------------------
# AC7 — requirements.txt lists google-adk, mcp[cli], and security when pii
# T016 [P]
# ---------------------------------------------------------------------------


def test_requirements_has_adk_and_mcp(
    spec_example_dict: dict[str, Any],
    tmp_path: Path,
) -> None:
    """AC7 — requirements.txt contains google-adk, mcp[cli].
    When pii.enabled=True, also references security package.
    """
    spec = load_spec(spec_example_dict)
    render(spec, tmp_path)

    reqs = (tmp_path / "generated_agent" / "requirements.txt").read_text(encoding="utf-8")

    assert "google-adk" in reqs
    assert "mcp" in reqs
    # PII is enabled in spec_example
    assert "security" in reqs


def test_requirements_no_security_when_pii_disabled(tmp_path: Path) -> None:
    """AC7 (complement) — no security in requirements when pii.enabled=False."""
    spec = load_spec(
        {
            "name": "no-pii",
            "description": "no pii",
            "model": "gemini-2.5-flash",
            "instruction": "help",
            "mcp_servers": [{"name": "srv", "url": "http://srv:8001/sse"}],
            "http_tools": [],
            "guardrails": {"pii": {"enabled": False, "allow_list": []}},
        }
    )
    render(spec, tmp_path)

    reqs = (tmp_path / "generated_agent" / "requirements.txt").read_text(encoding="utf-8")
    assert "google-adk" in reqs
    assert "mcp" in reqs
    assert "security" not in reqs


# ---------------------------------------------------------------------------
# AC8 — tool_filter rendered when non-empty
# T017 [P]
# ---------------------------------------------------------------------------


def test_tool_filter_rendered(tmp_path: Path) -> None:
    """AC8 — McpToolset includes tool_filter parameter when spec has non-empty list."""
    spec = load_spec(
        {
            "name": "filter-agent",
            "description": "Agent with tool filter",
            "model": "gemini-2.5-flash",
            "instruction": "Filter tools.",
            "mcp_servers": [
                {
                    "name": "ocr",
                    "url": "http://ocr:8001/sse",
                    "tool_filter": ["extract_exams_from_image"],
                }
            ],
            "http_tools": [],
        }
    )
    render(spec, tmp_path)

    agent_py = (tmp_path / "generated_agent" / "agent.py").read_text(encoding="utf-8")

    assert "tool_filter" in agent_py
    assert "extract_exams_from_image" in agent_py


def test_tool_filter_omitted_when_none(tmp_path: Path) -> None:
    """AC8 (complement) — tool_filter not present when spec.tool_filter is None."""
    spec = load_spec(
        {
            "name": "no-filter-agent",
            "description": "Agent without tool filter",
            "model": "gemini-2.5-flash",
            "instruction": "Use all tools.",
            "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
            "http_tools": [],
        }
    )
    render(spec, tmp_path)

    agent_py = (tmp_path / "generated_agent" / "agent.py").read_text(encoding="utf-8")

    assert "tool_filter" not in agent_py


# ---------------------------------------------------------------------------
# AC12 — Template injection rejected (allow-list on identifier fields)
# T034 [P]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malicious_name",
    [
        # Classic Jinja2 template escape + Python code
        "x}};import os;os.system('id')",
        # Single-quote injection
        "'; import os; os.system('x')",
        # Triple-quote injection
        '""";\nimport os; os.system("x")',
        # Backslash injection
        "agent\\x00name",
        # Unicode lookalike
        "agent\u0041gent",  # 'A' lookalike in a name that would pass visually
        # Uppercase (not in allow-list)
        "Agent",
        # Whitespace
        "agent name",
        # Empty string
        "",
    ],
)
def test_template_injection_rejected(malicious_name: str) -> None:
    """AC12 — AgentSpec with name containing injection characters raises TranspilerError
    before render via the generator allow-list check (second defence layer).

    The Bloco 1 schema pattern ^[a-z0-9][a-z0-9-]*$ would already reject most
    injection payloads; this test exercises the generator-level re-check by
    constructing an AgentSpec with a tampered name after Pydantic validation.

    Covers all M4 injection variants: classic Jinja2 escape, single-quote,
    triple-quote, backslash, unicode, uppercase, whitespace, empty string.
    """
    spec = load_spec(
        {
            "name": "valid-name",
            "description": "test",
            "model": "gemini-2.5-flash",
            "instruction": "help",
            "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
            "http_tools": [],
        }
    )

    # Bypass Pydantic frozen model to inject a dangerous value directly.
    # object.__setattr__ is used because AgentSpec has model_config frozen=True.
    object.__setattr__(spec, "name", malicious_name)

    with pytest.raises(TranspilerError) as exc_info:
        _context(spec)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_SCHEMA"
    assert "name" in (err.path or "").lower() or "name" in err.message.lower()


# ---------------------------------------------------------------------------
# AC13 — agent.py size cap enforced at 100 KB
# T035 [P] [DbC] — render.Post (cap 100 KB)
# ---------------------------------------------------------------------------


def test_agent_py_size_cap_enforced(
    spec_example_dict: dict[str, Any],
    tmp_path: Path,
) -> None:
    """AC13 [DbC render.Post] — agent.py > 100 KB raises E_TRANSPILER_RENDER_SIZE.

    Monkeypatches _render_template to emit a 101 KB string for agent.py.j2
    (simulates a pathological spec without needing a real oversized spec.json).
    """
    spec = load_spec(spec_example_dict)

    original = gen_mod._render_template  # noqa: SLF001

    def _huge_render(env: Any, template_name: str, ctx: Any) -> str:
        if template_name == "agent.py.j2":
            # Return > 100 KB of valid Python (comment-only lines to pass ast.parse)
            # "# padding\n" is 10 bytes; 10_300 * 10 = 103_000 bytes > 102_400 (100 KB)
            lines = ["# padding\n"] * 10_300
            return "".join(lines)
        return original(env, template_name, ctx)

    with patch.object(gen_mod, "_render_template", side_effect=_huge_render):
        with pytest.raises(TranspilerError) as exc_info:
            render(spec, tmp_path)

    err = exc_info.value
    assert err.code == "E_TRANSPILER_RENDER_SIZE"
    assert "100 KB" in err.message or "100" in err.message
    assert err.context is not None
    assert err.context.get("cap_bytes") == 100 * 1024


# ---------------------------------------------------------------------------
# Context builder unit test
# ---------------------------------------------------------------------------


def test_context_builder_produces_correct_keys(spec_example_dict: dict[str, Any]) -> None:
    """_context() produces all expected keys and correct types."""
    spec = load_spec(spec_example_dict)
    ctx = _context(spec)

    assert set(ctx.keys()) == {
        "name", "description", "model", "instruction",
        "mcp_servers", "http_tools", "pii_enabled",
    }
    assert ctx["name"] == "medical-order-agent"
    assert ctx["pii_enabled"] is True
    assert len(ctx["mcp_servers"]) == 2
    assert len(ctx["http_tools"]) == 1


def test_context_builder_mcp_tool_filter_none() -> None:
    """_context() preserves tool_filter=None when not specified."""
    spec = load_spec(
        {
            "name": "agent",
            "description": "d",
            "model": "gemini-2.5-flash",
            "instruction": "i",
            "mcp_servers": [{"name": "ocr", "url": "http://ocr:8001/sse"}],
            "http_tools": [],
        }
    )
    ctx = _context(spec)
    assert ctx["mcp_servers"][0]["tool_filter"] is None
