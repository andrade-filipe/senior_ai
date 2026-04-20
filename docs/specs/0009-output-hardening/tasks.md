---
id: 0009-output-hardening
status: todo
---

> **Nota 2026-04-20**: Camada A (T010–T012, T040 reinterpretado, T042) foi **partialmente superseded** por spec 0010 + ADR-0010. Ver `spec.md § Atualização 2026-04-20`. T013 e T041 permanecem `done`. Camadas B e C (T014–T029, T050–T063) permanecem ativas.

## Setup

- [ ] T001 — criar `docs/EVIDENCE/0009-output-hardening.md` vazio com frontmatter
- [ ] T002 — responder [NEEDS CLARIFICATION] Q1–Q4 do `spec.md`; atualizar spec `status: approved`

## Tests (TDD RED)

Cada teste **deve falhar** antes da implementação correspondente. `[DbC]` marca teste que exercita linha da tabela DbC do `plan.md`.

### Camada A — Fixture reliability

- [ ] T010 [P] [DbC] — escrever `ocr_mcp/tests/test_fixtures_roundtrip.py::test_canonical_png_lookup_matches` — lê `ocr_mcp/tests/fixtures/sample_medical_order.png`, base64-encode, chama `lookup()`, espera a lista `_SAMPLE_EXAMS` não vazia (AC1)
- [ ] T011 [P] [DbC] — escrever `ocr_mcp/tests/test_register_fixture.py::test_register_then_lookup_returns_registered_exams` — chama `register_fixture(path, ["X"])`, depois `lookup()` com base64 do mesmo PNG devolve `["X"]` (AC2)
- [ ] T012 [P] — escrever `ocr_mcp/tests/test_register_fixture.py::test_register_twice_updates` — segundo `register_fixture` sobrescreve entrada anterior (AC2)
- [ ] T013 — escrever `ocr_mcp/tests/test_server_ocr_hash_log.py::test_lookup_emits_hash_log` — captura logs, afirma evento `ocr.lookup.hash` com o digest decodificado

### Camada B — Tolerant RunnerOutput

- [ ] T014 [P] [DbC] — `tests/generated_agent/test_runner_result.py::test_success_shape_parses` — dict canônico de sucesso → `RunnerSuccess` (AC3)
- [ ] T015 [P] [DbC] — `tests/generated_agent/test_runner_result.py::test_error_shape_parses` — dict `{"status":"error","error":{...}}` → `RunnerError` (AC4)
- [ ] T016 [P] — `tests/generated_agent/test_runner_result.py::test_missing_status_rejected` — dict sem `status` → `pydantic.ValidationError`
- [ ] T017 [P] — `tests/generated_agent/test_runner_result.py::test_mixed_shape_rejected` — `{"status":"success","error":{...}}` é rejeitado
- [ ] T018 [P] [DbC] — `tests/generated_agent/test_parse_runner_output.py::test_success_round_trip_returns_runner_success` — raw evento sucesso → `RunnerSuccess` (AC3)
- [ ] T019 [P] [DbC] — `tests/generated_agent/test_parse_runner_output.py::test_error_envelope_exits_with_code_4` — raw evento erro → `SystemExit(4)` com envelope em stderr (AC4)

### Camada C — Validator-pass

- [ ] T024 [P] [DbC] — `tests/generated_agent/test_validator_pass.py::test_returns_none_on_timeout` — mock `genai.Client` levanta `TimeoutError`; `_run_validator_pass` devolve `None`, não levanta (AC7)
- [ ] T025 [P] [DbC] — `tests/generated_agent/test_validator_pass.py::test_returns_json_string_on_success` — mock devolve JSON válido; `_run_validator_pass` devolve a string (AC5)
- [ ] T026 [P] — `tests/generated_agent/test_validator_pass.py::test_returns_none_on_http_error` — mock levanta `google.api_core.exceptions.ServiceUnavailable`; devolve `None` (AC7)
- [ ] T027 [P] — `tests/generated_agent/test_validator_pass.py::test_respects_max_input_bytes` — input maior que cap; não chama genai; devolve `None`
- [ ] T028 — `tests/generated_agent/test_parse_runner_output.py::test_validator_pass_applied_on_drift` — `AGENT_VALIDATOR_PASS_ENABLED=true`, raw drift, validator mock devolve JSON canônico → `RunnerSuccess` (AC5)
- [ ] T029 — `tests/generated_agent/test_parse_runner_output.py::test_validator_pass_disabled_by_default` — sem env var, raw drift → `SystemExit(3)` (AC6)

### E2E

- [ ] T030 — `tests/e2e/test_full_flow.py::test_happy_path_canonical_fixture` — pula se `.env` ausente; roda `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`; afirma exit 0 + tabela ASCII no stdout (AC8)

## Implementation (TDD GREEN)

### Camada A

- [ ] T040 — implementar `register_fixture(image_path: str, exams: list[str]) -> str` em `ocr_mcp/ocr_mcp/fixtures.py` — popula `FIXTURES[sha256]=list(exams)`; devolve digest (T011, T012)
- [ ] T041 — adicionar log estruturado `ocr.lookup.hash` em `ocr_mcp/ocr_mcp/server.py` no call de `lookup()` (T013)
- [ ] T042 — se T010 falhou: investigar divergência de hash via log T041 durante `docker compose run` e adicionar entrada ao `FIXTURES` via `register_fixture` no server startup (T010) — **depende do resultado do log**

### Camada B

- [ ] T050 — substituir `_RunnerOutput` em `generated_agent/__main__.py` por `RunnerSuccess | RunnerError` com discriminador `status`; adicionar `ExamResolution`, `RunnerErrorDetail` (T014–T017)
- [ ] T051 — atualizar `_parse_runner_output` para devolver `RunnerResult` e chamar `_exit_error(exit_code=4)` em branch `RunnerError` (T018, T019)
- [ ] T052 — atualizar `main()` para bifurcar: `RunnerSuccess` → tabela ASCII (atual); `RunnerError` → já tratou em `_exit_error`
- [ ] T053 — atualizar `docs/fixtures/spec.example.json` instruction: adicionar `"status":"success"` no schema canônico; adicionar envelope de erro canônico; regerar agent.py via `uv run python -m transpiler docs/fixtures/spec.example.json generated_agent`
- [ ] T054 — regenerar snapshots transpiler: `uv run python -m pytest transpiler/tests/test_snapshots.py --force-regen`

### Camada C

- [ ] T060 — criar `generated_agent/validator.py` com `_run_validator_pass(raw_text, correlation_id) -> str | None` (T024–T027)
- [ ] T061 — adicionar env vars `AGENT_VALIDATOR_PASS_ENABLED`, `VALIDATOR_MODEL`, `VALIDATOR_TIMEOUT_SECONDS`, `VALIDATOR_MAX_INPUT_BYTES` ao `.env.example` + `docs/CONFIGURATION.md`
- [ ] T062 — wirar `_parse_runner_output` para chamar validator no branch `pydantic.ValidationError` quando flag ligada (T028, T029)
- [ ] T063 — propagar env vars em `docker-compose.yml` service `generated-agent`

## Refactor (TDD REFACTOR)

- [ ] T070 — extrair `_extract_text_from_event` se `_parse_runner_output` e `_run_validator_pass` duplicarem lógica de varredura de `content.parts`
- [ ] T071 — consolidar constantes `E_*` em `generated_agent/errors.py` (hoje espalhadas em `__main__.py`)

## Evidence

- [ ] T090 — rodar `uv run pytest ocr_mcp/tests/ tests/generated_agent/ -q` e capturar saída em `docs/EVIDENCE/0009-output-hardening.md`
- [ ] T091 — rodar E2E real e capturar transcript (stdout + stderr) em `docs/EVIDENCE/0009-output-hardening.md` seção `## E2E`
- [ ] T092 — atualizar `docs/adr/0008-robust-validation-policy.md` com addendum listando `E_AGENT_OUTPUT_REPORTED_ERROR` (exit 4)
- [ ] T093 — atualizar `ai-context/STATUS.md` marcando bloco 0009 como done

## Paralelismo

- Testes camada A (T010–T013) podem rodar em paralelo com testes camada B (T014–T019) — arquivos distintos.
- T024–T027 dependem de T060 existir como stub; marcar `in_progress` depois de stub.
- T053 (regen agent.py) **bloqueia** qualquer run E2E até T054 (regen snapshots) estar verde — executar em sequência.
- T042 é **condicional**: só abre se T010 falhar após T041 estar em prod. Não bloqueia camadas B/C.
