---
id: 0010-pre-ocr-invocation
status: done
---

## Setup

- [x] T001 — criar `docs/EVIDENCE/0010-pre-ocr-invocation.md` (stub com frontmatter)
- [x] T002 — addendum em `docs/specs/0009-output-hardening/spec.md` marcando Camada A como partialmente superseded por 0010; cross-link em `tasks.md` e `plan.md` da 0009

## Tests (TDD RED)

Cada teste **deve falhar** antes da implementação correspondente. `[DbC]` marca teste que exercita linha da tabela DbC do `plan.md`.

- [x] T010 [P] [DbC] — `tests/generated_agent/test_preocr.py::test_calls_mcp_and_returns_exams` — mock `mcp.client.sse.sse_client` + `ClientSession`; asserta `session.call_tool("extract_exams_from_image", {"image_base64": <b64>})` e retorno `list[str]` (AC1)
- [x] T011 [P] [DbC] — `tests/generated_agent/test_preocr.py::test_build_prompt_contains_exam_list_and_no_inline_data` — chama `_build_preocr_prompt(["Hemograma"])`; asserta Part único com texto `"EXAMES DETECTADOS (OCR pré-executado pelo CLI):"` e ausência de `inline_data` em todos os parts (AC3)
- [x] T012 [P] [DbC] — `tests/generated_agent/test_agent_topology.py::test_ocr_tool_not_in_agent_tools` — constrói `_build_agent("cid")` e asserta que nenhum McpToolset expõe `extract_exams_from_image` (via `tool_filter=[]` ou toolset ausente) (AC4)
- [x] T013 [P] [DbC] — `tests/generated_agent/test_preocr.py::test_timeout_raises_preocr_error` — mock que dorme além de `timeout_s`; espera `_PreOcrError(code="E_MCP_UNAVAILABLE")` (AC6)
- [x] T014 [P] — `tests/generated_agent/test_main_preocr_wiring.py::test_main_aborts_on_empty_exam_list` — monkey-patch `_run_preocr` para retornar `[]`; espera `SystemExit(4)` e envelope `E_OCR_UNKNOWN_IMAGE` em stderr (AC2)
- [x] T015 [P] — `tests/generated_agent/test_main_preocr_wiring.py::test_main_aborts_on_mcp_unavailable` — monkey-patch `_run_preocr` para levantar `_PreOcrError(E_MCP_UNAVAILABLE)`; espera `SystemExit(5)` (AC6)
- [x] T016 — teste técnico: `transpiler/tests/test_snapshots.py` roda com o snapshot **antigo** e falha (sinaliza necessidade de regen em T026); não é um AC em si

## Implementation (TDD GREEN)

- [x] T020 — implementar `generated_agent/preocr.py` com `_run_preocr` e `_PreOcrError`; mapeamento de erros conforme plan.md § Contratos (T010, T013)
- [x] T021 — refatorar `generated_agent/__main__.py::main` para (a) ler bytes da imagem, (b) chamar `_run_preocr`, (c) tratar aborts AC2/AC6, (d) passar `exams` adiante; nova constante `_E_MCP_UNAVAILABLE` e exit code `5` (T014, T015)
- [x] T022 — refatorar `_run_agent` para receber `exams: list[str]`; remover `image_bytes`/`mime_type`; usar `_build_preocr_prompt` para construir `Content` sem `inline_data` (T011)
- [x] T023 — editar `docs/fixtures/spec.example.json`: (a) adicionar `"exposed": false` ao OCR server; (b) reescrever `instruction` removendo "1. Chame extract_exams_from_image…" e inserindo "Voce recebera um bloco 'EXAMES DETECTADOS' no prompt; use-o como ponto de partida do passo 2"
- [x] T024 — `transpiler/transpiler/schema.py` + `transpiler/transpiler/templates/agent.py.j2`: adicionar campo `exposed: bool = True` em `McpServerSpec`; template emite `tool_filter=[]` (ou McpToolset omitido) quando `exposed=false`; snapshot test será atualizado em T026
- [x] T025 — regerar `generated_agent/agent.py` via `uv run python -m transpiler docs/fixtures/spec.example.json generated_agent` (bloqueia após T023 e T024)
- [x] T026 — regerar snapshots do transpiler: `uv run pytest transpiler/tests/test_snapshots.py --snapshot-update` (bloqueia após T024 + T025)
- [x] T027 — adicionar envs `PREOCR_MCP_TIMEOUT_SECONDS=10` e `PREOCR_MCP_CONNECT_RETRIES=1` em `.env.example` + seção `docs/CONFIGURATION.md § generated-agent` + propagar em `docker-compose.yml` service `generated-agent`
- [x] T028 — adicionar `E_MCP_UNAVAILABLE` (exit 5) em `docs/ARCHITECTURE.md § Códigos de erro consolidados`; constante `_E_MCP_UNAVAILABLE` em `generated_agent/__main__.py`

## Refactor (TDD REFACTOR)

- [x] T030 — extrair `_json_dump_exams(exams: list[str]) -> str` se Camada B da 0009 e pré-OCR duplicarem serialização (padrão JSON com `ensure_ascii=False`)
- [x] T031 — se o OCR-MCP continuar retornando `[]` para a fixture canônica, patch curto no server OCR em `ocr_mcp/ocr_mcp/fixtures.py` para registrar `sample_medical_order.png` via `register_fixture` no startup (reuso de T040 da 0009)

## Evidence

- [x] T090 — rodar `uv run pytest tests/generated_agent/ transpiler/tests/ -q`; capturar saída em `docs/EVIDENCE/0010-pre-ocr-invocation.md § ## Unit`
- [x] T091 — rodar E2E real (`docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`, `.env` com `GEMINI_MODEL=gemini-2.5-flash-lite`) e capturar transcript em `docs/EVIDENCE/0010-pre-ocr-invocation.md § ## E2E`
- [x] T092 — atualizar `ai-context/STATUS.md` fechando bloco 10 (`done`) e cross-linkando nota em bloco 9 (Camada A superseded por 0010)
- [x] T093 — atualizar `docs/EVIDENCE/0009-output-hardening.md § ## Pre-OCR discovery (2026-04-20)` com trechos do log que motivaram esta spec

## Paralelismo

- T010–T015 podem rodar em paralelo — arquivos distintos (`test_preocr.py`, `test_agent_topology.py`, `test_main_preocr_wiring.py`).
- T024 bloqueia T025, que bloqueia T026 — sequencial.
- T023 + T024 podem ser feitos em paralelo por agentes diferentes (spec vs template); ambos bloqueiam T025.
- T020–T022 podem ser feitos em paralelo por um único agente (adk-mcp-engineer); importam recíprocos via `from generated_agent.preocr import _run_preocr`.
