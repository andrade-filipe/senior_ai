---
id: 0002-transpiler-mvp
status: todo
---

## Setup

- [ ] T001 — Adicionar `jinja2^3.1` e `pytest-regressions^2` ao `transpiler/pyproject.toml` (além das deps do Bloco 1).
- [ ] T002 — Criar diretório `transpiler/templates/` com arquivos vazios: `agent.py.j2`, `__init__.py.j2`, `requirements.txt.j2`, `Dockerfile.j2`, `.env.example.j2`.
- [ ] T003 — Criar `transpiler/generator.py` e `transpiler/cli.py` e `transpiler/__main__.py` como placeholders que levantam `NotImplementedError`.
- [ ] T004 [P] — Criar diretório de snapshots `tests/transpiler/snapshots/` e fixture `spec_example_json_path` apontando para `docs/fixtures/spec.example.json` (commitado no Bloco 6; usar fallback inline para começar).

## Tests (TDD RED)

- [ ] T010 [P] — Escrever teste falhando para [AC1] em `tests/transpiler/test_generator.py::test_generates_package_files` (lista esperada de arquivos existe após render).
- [ ] T011 [P] [DbC] — Escrever teste falhando para [AC2] em `tests/transpiler/test_generator.py::test_deterministic_output` (duas renders em tmpdirs distintos → `filecmp.dircmp`) — DbC: `render.Invariant` (determinismo).
- [ ] T012 [P] [DbC] — Escrever teste falhando para [AC3] em `tests/transpiler/test_generator.py::test_generated_py_is_parseable` (roda `ast.parse` em `agent.py` gerado) — DbC: `render.Post` (gate `ast.parse`).
- [ ] T013 [P] — Escrever teste falhando para [AC4] em `tests/transpiler/test_cli.py::test_cli_exits_1_on_schema_error`.
- [ ] T014 [P] — Escrever teste falhando para [AC5] em `tests/transpiler/test_generator.py::test_syntax_error_raised_when_template_broken` (template mock com código inválido).
- [ ] T015 [P] — Escrever teste falhando para [AC6] em `tests/transpiler/test_generator.py::test_agent_py_has_mcp_toolset_import` (inspeciona conteúdo renderizado).
- [ ] T016 [P] — Escrever teste falhando para [AC7] em `tests/transpiler/test_generator.py::test_requirements_has_adk_and_mcp` (e `security` se `pii.enabled`).
- [ ] T017 [P] — Escrever teste falhando para [AC8] em `tests/transpiler/test_generator.py::test_tool_filter_rendered` (spec com `tool_filter=["x"]`).
- [ ] T018 [P] — Escrever snapshot test para [AC9] em `tests/transpiler/test_snapshots.py::test_example_snapshot` via `pytest-regressions.data_regression`.
- [ ] T033 [P] [DbC] — Escrever teste falhando para [AC11] em `tests/transpiler/test_cli.py::test_output_dir_path_traversal_rejected` (passa `-o ../../etc` e `-o /etc` → CLI exit code ≠ 0, stderr cita `E_TRANSPILER_RENDER` e "output_dir fora do projeto") — DbC: `render.Pre` (output_dir dentro do cwd).
- [ ] T034 [P] — Escrever teste falhando para [AC12] em `tests/transpiler/test_generator.py::test_template_injection_rejected` (monta `AgentSpec` via bypass com `name="x}};import os"` → `generator.render` levanta `TranspilerError` antes de render; reforço do AC3 do Bloco 1).
- [ ] T035 [P] [DbC] — Escrever teste falhando para [AC13] em `tests/transpiler/test_generator.py::test_agent_py_size_cap_enforced` (spec com payload inflado via `instruction` próximo do cap, monkey-patch do template para emitir > 100 KB → `TranspilerError(code="E_TRANSPILER_RENDER_SIZE")`) — DbC: `render.Post` (cap 100 KB).
- [ ] T019 — Rodar `uv run pytest tests/transpiler/` e confirmar que **todos** os testes novos falham (RED).

## Implementation (TDD GREEN)

- [ ] T020 — Implementar `transpiler/templates/agent.py.j2` emitindo `from google.adk.agents import LlmAgent`, `McpToolset(connection_params=StreamableHTTPConnectionParams(url=...))` por item em `mcp_servers`, OpenAPI toolset por item em `http_tools`, `before_model_callback` condicional (AC6, AC7, AC8).
- [ ] T021 — Implementar `transpiler/templates/__init__.py.j2` (import `root_agent`).
- [ ] T022 — Implementar `transpiler/templates/requirements.txt.j2` listando `google-adk`, `mcp[cli]`, condicionalmente `security` (AC7).
- [ ] T023 — Implementar `transpiler/templates/Dockerfile.j2` (referenciado pelo Bloco 7 AC12).
- [ ] T024 — Implementar `transpiler/templates/.env.example.j2` com as variáveis de [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Variáveis de ambiente".
- [ ] T025 — Implementar `transpiler/generator.py::render(spec, output_dir)` com `jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)` e loop determinístico de escrita (AC1, AC2).
- [ ] T026 — Implementar gate `ast.parse` em `generator.py` para cada `.py` emitido, levantando `TranspilerError(code="E_TRANSPILER_SYNTAX")` com nome do arquivo (AC3, AC5).
- [ ] T027 — Implementar `transpiler/cli.py` com argparse (`spec_path`, `-o`, `-v`) e mapeamento de exceções para códigos de saída 0/1/2/3 (AC4).
- [ ] T028 — Implementar `transpiler/__main__.py` chamando `cli.main()`.
- [ ] T029 — Congelar snapshots inicial via `uv run pytest tests/transpiler/test_snapshots.py --force-regen` e commitar (AC9).

## Refactor (TDD REFACTOR)

- [ ] T030 — Extrair `generator._context(spec)` como função pura para montar o dict passado aos templates (testável isoladamente).
- [ ] T031 — Adicionar `--help` descritivo na CLI e docstring de módulo em cada template (`{# ... #}`).
- [ ] T032 — Rodar `uv run ruff check .` e `uv run mypy --strict transpiler/` até zero warnings.

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0002-transpiler-mvp.md`: `uv run pytest tests/transpiler/ --cov=transpiler --cov-report=term`, relatório de cobertura ≥ 80 %, diff-nulo entre duas renders (AC2), hash do `spec.example.json` usado.
- [ ] T091 — Anexar excerto do `agent.py` gerado (primeiras 40 linhas) como prova de AC6.

## Paralelismo

Tarefas `[P]` (T004, T010–T018) rodam em paralelo nos arquivos de teste. T019 é gate. Dentro da seção GREEN, T020–T024 (templates) podem rodar em paralelo — arquivos `.j2` distintos; T025 precisa dos templates prontos; T026 e T027 são sequenciais à T025.
