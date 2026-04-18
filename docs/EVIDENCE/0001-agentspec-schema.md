# Evidência — Bloco 0001 · Schema `AgentSpec` e validação do JSON de entrada

- **Spec**: [`docs/specs/0001-agentspec-schema/spec.md`](../specs/0001-agentspec-schema/spec.md)
- **Status**: `done` — fechado em 2026-04-18.
- **Ambiente**: Windows 11, PowerShell 5.1, `uv 0.11.7`, Python `3.12.13`.
- **Pyproject**: `transpiler/pyproject.toml` (per-service, ADR-0005).

## Resumo

- 13 testes unitários em `transpiler/tests/` cobrem AC1–AC7, AC9–AC13.
- Cobertura medida: **97.73 %** (limite ADR-0004: 80 %).
- `mypy --strict` limpo em `transpiler/` (0 erros em 3 arquivos).
- Nenhum bloqueador; review independente (`code-reviewer`) aprovou com ressalvas menores — todas fixadas.

## Commands & outputs

### 1. `uv sync` (inclui `dev` group — PEP 735)

```
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 19 packages in 25ms
      Built transpiler @ file:///C:/Users/Filipe/Desktop/Senior_IA/transpiler
Prepared 14 packages in 2.97s
Installed 14 packages in 1.04s
 + pytest==8.4.2
 + pytest-cov==5.0.0
 + mypy==1.20.1
 + ruff==0.15.11
 + pydantic==2.13.2  (runtime)
 ...
```

### 2. `uv run pytest --cov=transpiler --cov-report=term-missing -v`

```
platform win32 -- Python 3.12.13, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\Filipe\Desktop\Senior_IA\transpiler
configfile: pyproject.toml
testpaths: tests
plugins: cov-5.0.0
collected 13 items

tests/test_errors.py::test_format_challenge_error_shape PASSED                 [  7%]
tests/test_errors.py::test_format_challenge_error_optional_fields_none PASSED  [ 15%]
tests/test_schema.py::test_valid_example_parses PASSED                         [ 23%]
tests/test_schema.py::test_invalid_model_rejected PASSED                       [ 30%]
tests/test_schema.py::test_name_pattern_rejected PASSED                        [ 38%]
tests/test_schema.py::test_extra_field_rejected PASSED                         [ 46%]
tests/test_schema.py::test_missing_required_field_rejected PASSED              [ 53%]
tests/test_schema.py::test_invalid_url_rejected PASSED                         [ 61%]
tests/test_schema.py::test_roundtrip_json PASSED                               [ 69%]
tests/test_schema.py::test_duplicate_mcp_server_names_rejected PASSED          [ 76%]
tests/test_schema.py::test_list_caps_enforced PASSED                           [ 84%]
tests/test_schema.py::test_string_caps_enforced PASSED                         [ 92%]
tests/test_schema.py::test_spec_json_size_cap PASSED                           [100%]

---------- coverage: platform win32, python 3.12.13-final-0 ----------
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
transpiler/__init__.py       3      0   100%
transpiler/errors.py        19      1    95%   46
transpiler/schema.py       110      2    98%   286, 383
------------------------------------------------------
TOTAL                      132      3    98%

Required test coverage of 80.0% reached. Total coverage: 97.73%

================================ 13 passed in 0.64s =================================
```

### 3. `uv run mypy --strict transpiler/`

```
Success: no issues found in 3 source files
```

## Mapeamento AC → teste

| AC | Teste | Arquivo |
|---|---|---|
| AC1 | `test_valid_example_parses` | `tests/test_schema.py` |
| AC2 | `test_invalid_model_rejected` | `tests/test_schema.py` |
| AC3 | `test_name_pattern_rejected` | `tests/test_schema.py` |
| AC4 | `test_extra_field_rejected` | `tests/test_schema.py` |
| AC5 | `test_missing_required_field_rejected` | `tests/test_schema.py` |
| AC6 | `test_invalid_url_rejected` | `tests/test_schema.py` |
| AC7 | `test_roundtrip_json` | `tests/test_schema.py` |
| AC8 | cobertura 97.73 % (relatório pytest-cov acima) | — |
| AC9 | `test_duplicate_mcp_server_names_rejected` | `tests/test_schema.py` |
| AC10 | `test_list_caps_enforced` | `tests/test_schema.py` |
| AC11 | `test_string_caps_enforced` | `tests/test_schema.py` |
| AC12 | `test_spec_json_size_cap` | `tests/test_schema.py` |
| AC13 | `test_format_challenge_error_shape` + `test_format_challenge_error_optional_fields_none` | `tests/test_errors.py` |

> **AC13 — escopo parcial**: este bloco implementa `format_challenge_error(exc) -> dict` com o shape canônico de ADR-0008. O teste end-to-end da CLI (stderr linha-a-linha + exit code ≠ 0) está **diferido para o Bloco 0002**, que introduz o módulo CLI. Documentado em `docs/specs/0001-agentspec-schema/tasks.md` § Tests.

## Review independente

`code-reviewer` rodou com checklist de 4 eixos (AC conformance, DbC triple-trace, ADR-0008 error taxonomy, Clean Code). Veredito: **APROVADO COM RESSALVAS**. 0 issues críticos; 11 issues menores levantados, dos quais foram aplicados:

- **M2 + M7**: renomeada `_format_validation_error` → `format_validation_error` (pública, path estável), assinatura ajustada para `(path, context)` sem campo não-usado, docstring corrigida.
- **M5 (doc)**: `tasks.md` § Tests reescrito para diferir o CLI test ao Bloco 0002 e renumerar as tasks Refactor colididas (T030/T031 → T040/T041).
- **M10**: import `BeforeValidator` migrado para `from pydantic import BeforeValidator` (path público).
- **M7 (doc-vs-impl)**: `format_validation_error` agora com docstring coerente com o que faz.
- Mypy strict: removidos 4 `cast()` redundantes em `schema.py` e o import `cast` do módulo `typing`.

As demais ressalvas (M1 layout, M3/M4 asserts de mensagem, M6 colisão de tasks, M8 distinguir lista/string em mensagem `too_long`, M9 `__init__.py` em tests, M11 `deepcopy` em fixture) foram validadas como **já corrigidas** pelo primeiro pass do engineer ou pelo orquestrador antes do review final.

## Artefatos de código (para reprodutibilidade)

- `transpiler/pyproject.toml`
- `transpiler/transpiler/__init__.py`
- `transpiler/transpiler/errors.py` (`ChallengeError`, `TranspilerError`, `format_validation_error`, `format_challenge_error`)
- `transpiler/transpiler/schema.py` (`AgentSpec`, `McpServerSpec`, `HttpToolSpec`, `PiiGuardSpec`, `GuardrailSpec`, `load_spec`)
- `transpiler/tests/conftest.py`
- `transpiler/tests/test_schema.py`
- `transpiler/tests/test_errors.py`

Todos exportados via `transpiler/__init__.py`.

## Próximo passo

Kickoff do **Bloco 0002 — Transpilador MVP (Jinja2 + generator + CLI)**. Este bloco é o único consumidor direto do schema deste bloco; nenhum outro bloco importa diretamente `transpiler.schema`.
