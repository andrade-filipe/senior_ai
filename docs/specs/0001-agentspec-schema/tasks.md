---
id: 0001-agentspec-schema
status: todo
---

## Setup

- [ ] T001 — Criar `transpiler/pyproject.toml` com dependências `pydantic^2.6`, `pytest^8`, `pytest-cov^5`, `mypy`, `ruff` (ADR-0005).
- [ ] T002 — Criar estrutura `transpiler/` com `__init__.py`, `errors.py`, `schema.py` vazios (apenas placeholders).
- [ ] T003 — Configurar `mypy --strict` para `transpiler/` em `transpiler/pyproject.toml` ([tool.mypy]) (GUIDELINES § 1).
- [ ] T004 [P] — Criar `tests/transpiler/__init__.py` e `tests/transpiler/conftest.py` com fixture `spec_example_dict` copiando o JSON de `docs/ARCHITECTURE.md`.

## Tests (TDD RED)

- [ ] T010 [P] [DbC] — Escrever teste falhando para [AC1] em `tests/transpiler/test_schema.py::test_valid_example_parses` (instancia `AgentSpec` e assere campos) — DbC: `AgentSpec.Invariant`.
- [ ] T011 [P] — Escrever teste falhando para [AC2] em `tests/transpiler/test_schema.py::test_invalid_model_rejected` (espera `TranspilerError(code="E_TRANSPILER_SCHEMA")`).
- [ ] T012 [P] — Escrever teste falhando para [AC3] em `tests/transpiler/test_schema.py::test_name_pattern_rejected` (nome com espaço/maiúscula).
- [ ] T013 [P] [DbC] — Escrever teste falhando para [AC4] em `tests/transpiler/test_schema.py::test_extra_field_rejected` (campo `memory_type`) — DbC: `AgentSpec.Invariant` (`extra="forbid"`).
- [ ] T014 [P] — Escrever teste falhando para [AC5] em `tests/transpiler/test_schema.py::test_missing_required_field_rejected` (omite `mcp_servers`).
- [ ] T015 [P] [DbC] — Escrever teste falhando para [AC6] em `tests/transpiler/test_schema.py::test_invalid_url_rejected` (cita path `mcp_servers.0.url`) — DbC: `McpServerSpec.Post` (URL validada como `AnyHttpUrl`).
- [ ] T016 [P] [DbC] — Escrever teste falhando para [AC7] em `tests/transpiler/test_schema.py::test_roundtrip_json` (dump + load mantém equivalência) — DbC: `load_spec.Invariant` (round-trip estável).
- [ ] T017 — Rodar `uv run pytest tests/transpiler/test_schema.py` e confirmar que **todos** os testes falham (RED acionável).
- [ ] T027 [DbC] — Escrever teste falhando para [AC9] em `tests/transpiler/test_schema.py::test_duplicate_mcp_server_names_rejected` (instancia `AgentSpec(mcp_servers=[{name:'x',...},{name:'x',...}])` e espera `ValidationError`/`TranspilerError` apontando `name` duplicado) — DbC: `McpServerSpec.Invariant` (name único entre irmãos).
- [ ] T028 [P] [DbC] — Escrever teste falhando para [AC10] em `tests/transpiler/test_schema.py::test_list_caps_enforced` (constrói spec com `mcp_servers` de 11 itens, `http_tools` de 21, `tool_filter` de 51; cada um → `TranspilerError(code="E_TRANSPILER_SCHEMA")` citando campo e cap) — DbC: `AgentSpec.Invariant` (caps ADR-0008).
- [ ] T029 [P] [DbC] — Escrever teste falhando para [AC11] em `tests/transpiler/test_schema.py::test_string_caps_enforced` (`name`/`description`/`instruction` com 501 chars; URL com 2049 chars → `E_TRANSPILER_SCHEMA` citando campo) — DbC: `AgentSpec.Invariant` e `McpServerSpec.Invariant` (caps de string ADR-0008).
- [ ] T030 [P] [DbC] — Escrever teste falhando para [AC12] em `tests/transpiler/test_schema.py::test_spec_json_size_cap` (arquivo de 1.1 MB → `load_spec(path)` levanta `E_TRANSPILER_SCHEMA` mencionando "1 MB", sem tentar `json.loads`) — DbC: `load_spec.Pre` (cap de tamanho antes de parse).
- [ ] T031 [P] — Escrever teste falhando para [AC13] em `tests/transpiler/test_cli.py::test_transpiler_error_serializes_to_canonical_shape` (invoca CLI com spec inválido, captura stderr, valida linhas `code`, `message`, `hint`, `path`, `context` e exit code ≠ 0 conforme ADR-0008).

## Implementation (TDD GREEN)

- [ ] T020 — Implementar `transpiler/errors.py` com `ChallengeError` base e `TranspilerError` (code/message/hint) — faz T010 quase passar.
- [ ] T021 — Implementar classes Pydantic em `transpiler/schema.py` conforme ADR-0006 + `ConfigDict(extra="forbid")` — faz T010, T013, T014 passarem.
- [ ] T022 — Implementar wrapper `load_spec(source)` que traduz `pydantic.ValidationError` em `TranspilerError(code="E_TRANSPILER_SCHEMA", ...)` com mensagem PT-BR citando `loc` — faz T011, T012, T015 passarem.
- [ ] T023 — Usar `AnyHttpUrl` em `McpServerSpec.url` e `HttpToolSpec.base_url` — reforça T015.
- [ ] T024 — Exportar API pública em `transpiler/__init__.py`: `AgentSpec`, `McpServerSpec`, `HttpToolSpec`, `PiiGuardSpec`, `GuardrailSpec`, `load_spec`, `TranspilerError`.
- [ ] T025 — Rodar `uv run pytest tests/transpiler/test_schema.py --cov=transpiler.schema --cov-report=term` e confirmar verde + cobertura ≥ 80 % (AC8).

## Refactor (TDD REFACTOR)

- [ ] T030 — Extrair helper `_format_validation_error(exc) -> str` se lógica de tradução PT-BR aparecer inline em T022; mover para `transpiler/errors.py`.
- [ ] T031 — Revisar docstrings (Google style) em todas as funções públicas (GUIDELINES § 1); rodar `mypy --strict`.

## Evidence

- [ ] T090 — Capturar `uv run pytest ... --cov --cov-report=term` e `uv run mypy --strict transpiler/` em `docs/EVIDENCE/0001-agentspec-schema.md` conforme template do Bloco 8.

## Paralelismo

Tarefas `[P]` (T004, T010–T016) podem rodar simultaneamente — arquivos de teste diferentes ou arquivos independentes. T017 é gate sequencial antes do GREEN. T020–T024 têm dependência sequencial (cada uma libera algum teste).
