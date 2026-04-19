# Evidência — Bloco 0002 · Transpilador MVP (Jinja2 + generator + CLI)

- **Spec**: [`docs/specs/0002-transpiler-mvp/spec.md`](../specs/0002-transpiler-mvp/spec.md)
- **Status**: `done` — fechado em 2026-04-18.
- **Ambiente**: Windows 11, `uv 0.11.7`, Python `3.12.13`.
- **Pyproject**: `transpiler/pyproject.toml` (per-service, ADR-0005).

## Resumo

- 53 testes em `transpiler/tests/` cobrem AC1–AC15 (schema, generator, CLI, snapshots).
- Cobertura medida: **95.16 %** (limite ADR-0004: 80 %).
- Transpilador determinístico: mesmo `spec.json` → mesmos arquivos gerados.
- Saída do `ast.parse` verificada após cada geração (gate de sintaxe AC13).

## Comandos reproduzíveis

```bash
cd transpiler
uv sync
uv run pytest --cov=transpiler --cov-report=term-missing -v
```

## Saída pytest resumida

```
platform win32 -- Python 3.12.13, pytest-8.4.2, pluggy-1.6.0
collected 53 items

tests/test_schema.py::...  PASSED  (13 tests)
tests/test_generator.py::... PASSED (15 tests)
tests/test_cli.py::...  PASSED  (12 tests)
tests/snapshots/...  PASSED  (13 snapshot tests)

53 passed in 6.29s
```

## Cobertura

```
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
transpiler/__init__.py        4      0   100%
transpiler/__main__.py        3      0   100%
transpiler/cli.py            51      7    86%   172-182
transpiler/errors.py         19      1    95%   46
transpiler/generator.py      58      3    95%   298, 347-348
transpiler/schema.py        113      1    99%   393
-------------------------------------------------------
TOTAL                       248     12    95%
Required test coverage of 80.0% reached. Total coverage: 95.16%
```

## CLI — saída de uma transpilação bem-sucedida

```bash
uv run python -m transpiler docs/fixtures/spec.example.json -o /tmp/out -v
```

Saída esperada:
```
Gerado em: /tmp/out/generated_agent
  .env.example
  Dockerfile
  __init__.py
  agent.py
  requirements.txt
```

## Snapshots

Cada fixture JSON em `tests/snapshots/` tem um arquivo `.py.snap` correspondente
verificado por `ast.parse`. Exemplo de saída gerada (`agent.py` inicial):

```python
"""Agente ADK gerado automaticamente pelo transpilador."""
import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

root_agent = LlmAgent(
    name="medical-order-agent",
    model="gemini-2.5-flash",
    instruction="...",
    tools=[
        McpToolset(connection_params=StdioServerParameters(...)),
    ],
)
```

## Mapeamento AC → teste

| AC | Teste principal | Arquivo |
|---|---|---|
| AC1 — transpilação ok | `test_render_generates_agent_py` | `test_generator.py` |
| AC2 — `ast.parse` gate | `test_generated_agent_py_is_valid_python` | `test_generator.py` |
| AC3 — CLI exit 0 | `test_cli_success_exit_zero` | `test_cli.py` |
| AC4 — CLI exit 1 schema | `test_cli_invalid_spec_exit_one` | `test_cli.py` |
| AC11 — path traversal | `test_cli_path_traversal_rejected` | `test_cli.py` |
| AC13 — shape canônico stderr | `test_cli_error_shape_on_stderr` | `test_cli.py` |
| AC14 — snapshots | todos em `tests/snapshots/` | — |
