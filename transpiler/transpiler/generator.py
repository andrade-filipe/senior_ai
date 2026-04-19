"""Transpiler generator — render AgentSpec to a generated_agent/ package.

Implements ADR-0002 (Jinja2 + ast.parse gate) and ADR-0008 (guardrails).

Design by Contract (full table in docs/specs/0002-transpiler-mvp/plan.md):
    render.Pre:
        spec is a validated AgentSpec (Bloco 1).
        output_dir.resolve() is relative to Path.cwd() (AC11, ADR-0008).
    render.Post:
        Every .py written passes ast.parse (AC3, AC5).
        agent.py size ≤ 100 KB after render (AC13, ADR-0008).
        Output directory is populated in sorted, stable order (AC2).
    render.Invariant:
        render(spec, dir_a) == render(spec, dir_b) byte-for-byte (AC2, determinism).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import jinja2

from transpiler.errors import TranspilerError
from transpiler.schema import AgentSpec

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_PY_MAX_BYTES = 100 * 1024  # 100 KB, ADR-0008 / AC13
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_OUTPUT_SUBDIR = "generated_agent"

# Identifier allow-list — matches AgentSpec.name pattern from Bloco 1 schema.
# Defence-in-depth: Bloco 1 already enforces this before the spec reaches us,
# but the generator re-validates before injecting into Jinja2 context
# (AC12: template injection guard).
_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Ordered list of template file names — deterministic write order (AC2).
_TEMPLATE_FILES: list[str] = [
    "__init__.py.j2",
    "agent.py.j2",
    "requirements.txt.j2",
    "Dockerfile.j2",
    ".env.example.j2",
]

# Output file name for each template (same order as _TEMPLATE_FILES).
_OUTPUT_FILES: list[str] = [
    "__init__.py",
    "agent.py",
    "requirements.txt",
    "Dockerfile",
    ".env.example",
]


# ---------------------------------------------------------------------------
# Jinja2 environment (singleton per process — templates are re-loaded each call
# to keep things simple and avoid stale caches in tests).
# ---------------------------------------------------------------------------


def _make_jinja_env() -> jinja2.Environment:
    """Create the Jinja2 Environment with code-generation settings.

    Returns:
        Configured jinja2.Environment with trim_blocks, lstrip_blocks,
        autoescape=False (Python output, not HTML), keep_trailing_newline=True.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(_TEMPLATES_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _context(spec: AgentSpec) -> dict[str, Any]:
    """Build the Jinja2 template context from an AgentSpec.

    Applies allow-list validation on identifier fields before injecting them
    into the template context (AC12: template injection guard).

    Pre:
        spec is a validated AgentSpec instance.
    Post:
        Returns a plain dict safe to pass to Jinja2 templates.
        All identifier fields pass _IDENTIFIER_RE.

    Args:
        spec: Validated AgentSpec from Bloco 1.

    Returns:
        Dict with keys: name, description, model, instruction, mcp_servers,
        http_tools, pii_enabled.

    Raises:
        TranspilerError: with code='E_TRANSPILER_SCHEMA' when identifier fields
            contain characters outside the allow-list (extra defence layer, AC12).
    """
    _assert_safe_identifier(spec.name, "name")
    for srv in spec.mcp_servers:
        _assert_safe_identifier(srv.name, f"mcp_servers[].name={srv.name!r}")
    for tool in spec.http_tools:
        _assert_safe_identifier(tool.name, f"http_tools[].name={tool.name!r}")

    mcp_list = [
        {
            "name": srv.name,
            "url": str(srv.url),
            "tool_filter": list(srv.tool_filter) if srv.tool_filter is not None else None,
        }
        for srv in spec.mcp_servers
    ]
    http_list = [
        {
            "name": tool.name,
            "base_url": str(tool.base_url),
            "openapi_url": str(tool.openapi_url) if tool.openapi_url is not None else None,
        }
        for tool in spec.http_tools
    ]

    return {
        "name": spec.name,
        "description": spec.description,
        "model": spec.model,
        "instruction": spec.instruction,
        "mcp_servers": mcp_list,
        "http_tools": http_list,
        "pii_enabled": spec.guardrails.pii.enabled,
    }


def _assert_safe_identifier(value: str, field: str) -> None:
    """Raise TranspilerError when a field value is not a safe identifier.

    Pre:
        value is a non-empty string.
    Post:
        Returns None when value matches _IDENTIFIER_RE.

    Args:
        value: The string to validate.
        field: Human-readable field name for the error message.

    Raises:
        TranspilerError: with code='E_TRANSPILER_SCHEMA' when value contains
            characters outside [a-z0-9][a-z0-9-]*.
    """
    if not _IDENTIFIER_RE.match(value):
        raise TranspilerError(
            code="E_TRANSPILER_SCHEMA",
            message=(
                f"Campo '{field}' contém caracteres inválidos para um identificador Python: "
                f"{value!r}. Use apenas letras minúsculas, dígitos, hífens e underscores."
            ),
            hint=(
                "Renomeie o campo para obedecer ao padrão ^[a-z0-9][a-z0-9-]*$. "
                "Exemplo válido: 'medical-order-agent'."
            ),
            path=field,
        )


# ---------------------------------------------------------------------------
# AST gate
# ---------------------------------------------------------------------------


def _ast_gate(content: str, filename: str) -> None:
    """Parse generated Python code with ast.parse; fail fast on syntax errors.

    Post:
        Returns None when content is valid Python.

    Args:
        content: Generated Python source code string.
        filename: Name of the output file (used in error messages).

    Raises:
        TranspilerError: with code='E_TRANSPILER_SYNTAX' when ast.parse raises
            SyntaxError, citing the filename and parse error details.
    """
    try:
        ast.parse(content)
    except SyntaxError as exc:
        raise TranspilerError(
            code="E_TRANSPILER_SYNTAX",
            message=(
                f"Template produziu Python inválido em '{filename}': {exc.msg} "
                f"(linha {exc.lineno})."
            ),
            hint="Abra issue — transpilador produziu código inválido.",
            path=filename,
            context={"syntax_error": str(exc), "lineno": exc.lineno},
        ) from exc


# ---------------------------------------------------------------------------
# Size cap
# ---------------------------------------------------------------------------


def _check_size_cap(content: str, filename: str) -> None:
    """Enforce the 100 KB cap on generated agent.py (ADR-0008 / AC13).

    Post:
        Returns None when len(content.encode()) ≤ 100 KB.

    Args:
        content: Rendered file content.
        filename: Output filename (used in error messages; only agent.py is
            currently capped, but the function is general).

    Raises:
        TranspilerError: with code='E_TRANSPILER_RENDER_SIZE' when the encoded
            byte size exceeds 100 KB.
    """
    size = len(content.encode("utf-8"))
    if size > _AGENT_PY_MAX_BYTES:
        raise TranspilerError(
            code="E_TRANSPILER_RENDER_SIZE",
            message=(
                f"Arquivo gerado '{filename}' excede 100 KB "
                f"(observado: {size:,} bytes)."
            ),
            hint=(
                "Revise o spec — instruction ou listas de tools grandes demais. "
                "Cap definido em ADR-0008."
            ),
            path=filename,
            context={"size_bytes": size, "cap_bytes": _AGENT_PY_MAX_BYTES},
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(spec: AgentSpec, output_dir: Path) -> None:
    """Render an AgentSpec to a generated_agent/ package under output_dir.

    Pre:
        spec is a validated AgentSpec (Bloco 1).
        output_dir.resolve() must be relative to Path.cwd() — path traversal
        guard enforced by CLI before calling this function (AC11).

    Post:
        output_dir / 'generated_agent' / * is written deterministically (AC2).
        Every .py file passes ast.parse (AC3, AC5).
        agent.py size ≤ 100 KB (AC13).

    Invariant:
        render(spec, dir_a) and render(spec, dir_b) produce byte-for-byte
        identical files for the same spec (AC2 — determinism).

    Args:
        spec: Validated AgentSpec to transpile.
        output_dir: Parent directory where generated_agent/ will be created.
            Must resolve to within the current working directory.

    Raises:
        TranspilerError: code='E_TRANSPILER_SCHEMA' for identifier violations.
        TranspilerError: code='E_TRANSPILER_SYNTAX' when ast.parse rejects output.
        TranspilerError: code='E_TRANSPILER_RENDER_SIZE' when agent.py > 100 KB.
        TranspilerError: code='E_TRANSPILER_RENDER' for unexpected Jinja2 errors.
    """
    ctx = _context(spec)
    env = _make_jinja_env()

    dest = output_dir / _OUTPUT_SUBDIR
    if dest.exists() and (dest / "agent.py").exists():
        raise TranspilerError(
            code="E_TRANSPILER_RENDER",
            message=(
                f"Diretório de saída '{dest.name}' já existe e contém 'agent.py'. "
                "Delete o diretório ou escolha outro caminho (--output)."
            ),
            hint=(
                "Delete o diretório de saída antes de re-gerar: "
                f"rm -rf {dest.name!r}.  "
                "Ou use -o para especificar um caminho diferente."
            ),
            path=str(dest),
        )
    dest.mkdir(parents=True, exist_ok=True)

    for template_name, output_name in zip(_TEMPLATE_FILES, _OUTPUT_FILES, strict=True):
        content = _render_template(env, template_name, ctx)

        if output_name.endswith(".py"):
            _ast_gate(content, output_name)

        if output_name == "agent.py":
            _check_size_cap(content, output_name)

        (dest / output_name).write_text(content, encoding="utf-8")


def _render_template(
    env: jinja2.Environment,
    template_name: str,
    ctx: dict[str, Any],
) -> str:
    """Load and render a single Jinja2 template.

    Args:
        env: Configured Jinja2 Environment.
        template_name: Template filename (e.g. 'agent.py.j2').
        ctx: Context dict to pass to the template.

    Returns:
        Rendered string content.

    Raises:
        TranspilerError: with code='E_TRANSPILER_RENDER' when Jinja2 raises
            TemplateError (e.g. undefined variable, template not found).
    """
    try:
        template = env.get_template(template_name)
        return template.render(**ctx)
    except jinja2.TemplateError as exc:
        raise TranspilerError(
            code="E_TRANSPILER_RENDER",
            message=f"Falha ao renderizar '{template_name}': {exc}",
            hint="Inspecione output_dir e template.",
            path=template_name,
            context={"jinja2_error": str(exc)},
        ) from exc
