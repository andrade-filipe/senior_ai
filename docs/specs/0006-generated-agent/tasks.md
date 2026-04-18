---
id: 0006-generated-agent
status: todo
---

## Setup

- [ ] T001 — Criar `docs/fixtures/` (se não existir) e colocar placeholder para `sample_medical_order.png` (R10) — conteúdo real definido após clarification.
- [ ] T002 — Escrever `docs/fixtures/spec.example.json` (R10) conforme schema do Bloco 1 + `instruction` incorporando patterns (§ 2 de AGENTIC_PATTERNS) — ver plan.md.
- [ ] T003 — Calcular `sha256(sample_medical_order.png)` e adicionar entrada correspondente em `ocr_mcp/fixtures.py` (coordenar com Bloco 3).
- [ ] T004 [P] — Criar `tests/generated_agent/__init__.py` e `tests/generated_agent/conftest.py` com fixtures `compose_up_subset` (ocr+rag+api) e `agent_runner`.
- [ ] T005 — Ajustar `transpiler/templates/agent.py.j2` (Bloco 2) se necessário para importar `before_model_callback` de `security` quando `guardrails.pii.enabled=True` (coordenar T020 deste bloco com T020 do Bloco 2).

## Tests (same-commit)

- [ ] T010 [P] — Teste [AC1] em `tests/generated_agent/test_e2e_flow.py::test_flow_within_5_tool_calls` — parseia logs `event=tool.called` e conta ≤ 5.
- [ ] T011 [P] — Teste [AC2] em `tests/generated_agent/test_e2e_flow.py::test_rag_calls_in_parallel` — checa timestamps em janela < 100 ms.
- [ ] T012 [P] — Teste [AC3] em `tests/generated_agent/test_e2e_flow.py::test_single_post_appointments`.
- [ ] T013 [P] [DbC] — Teste [AC4] em `tests/generated_agent/test_pii_callback.py::test_before_model_callback_strips_pii` — hook de teste do ADK mock + `llm_request.contents[].parts[].text` — DbC: `root_agent.Invariant` (`before_model_callback` registrado).
- [ ] T014 [P] — Teste [AC5] em `tests/generated_agent/test_e2e_flow.py::test_post_body_patient_ref_pattern`.
- [ ] T015 [P] — Teste [AC6] em `tests/generated_agent/test_integration.py::test_mcp_tool_discovery`.
- [ ] T016 [P] — Teste [AC7] em `tests/generated_agent/test_integration.py::test_openapi_tool_registered`.
- [ ] T017 [P] — Teste [AC8] em `tests/generated_agent/test_e2e_flow.py::test_rag_null_triggers_list_exams_degraded_mode`.
- [ ] T018 [P] — Teste [AC9] em `tests/generated_agent/test_e2e_flow.py::test_final_output_has_source_score_correlation_id`.
- [ ] T019 [P] — Teste [AC10] em `tests/generated_agent/test_e2e_flow.py::test_low_score_marked_inconclusive`.
- [ ] T020 [P] — Teste [AC11] em `tests/generated_agent/test_logging.py::test_tool_called_has_params_hash`.
- [ ] T021 [P] — Teste [AC12] em `tests/generated_agent/test_logging.py::test_correlation_id_propagated_across_services`.
- [ ] T022 [P] — Teste [AC13] em `tests/generated_agent/test_fixtures.py::test_fixtures_exist_and_spec_valid` (usa `transpiler.load_spec`).
- [ ] T023 [P] [DbC] — Teste [AC14] em `tests/generated_agent/test_e2e_flow.py::test_rag_none_triggers_list_exams_limit_20` (mocka `search_exam_code` → `None`; assere chamada a `list_exams(limit=20)` + apresentação ao usuário antes de reportar erro) — DbC: Retry policy.Post (`E_RAG_NO_MATCH` → zero retry, modo degradado).
- [ ] T024 [P] [DbC] — Teste [AC15] em `tests/generated_agent/test_retry.py::test_mcp_timeout_retries_once_with_500ms_delay` (mocka timeout; valida contagem de retries = 1, delay ≈ 500 ms, hint na exceção) — DbC: Retry policy.Post (`E_MCP_TIMEOUT` → 1 retry com 500 ms).
- [ ] T025 [P] [DbC] — Teste [AC16] em `tests/generated_agent/test_retry.py::test_api_validation_no_retry_reports_field_and_reason` (mocka 422; valida zero retries + mensagem citando campo + motivo) — DbC: Retry policy.Invariant (`E_API_VALIDATION` nunca retenta).
- [ ] T026 [P] — Teste [AC17] em `tests/generated_agent/test_final_table.py::test_ascii_table_snapshot` via `pytest-regressions.data_regression` (compara tabela ASCII final contra snapshot dourado).
- [ ] T027 [P] [DbC] — Teste [AC18] em `tests/generated_agent/test_guards.py::test_agent_timeout_300s` (monkey-patch `runner.run_async` com `sleep(301)` → runner retorna com `ChallengeError(code="E_AGENT_TIMEOUT")` no stderr; exit ≠ 0; nenhum POST à API registrado) — DbC: Runner CLI.Post (timeout 300 s).
- [ ] T028 [P] [DbC] — Teste [AC19] em `tests/generated_agent/test_guards.py::test_agent_output_invalid` (mocka `runner.run_async` retornando output inválido — JSON malformado ou schema faltando — → `ChallengeError(code="E_AGENT_OUTPUT_INVALID")`; zero retry contado) — DbC: Runner CLI.Post (output validation).
- [ ] T029 [P] [DbC] — Teste [AC21] em `tests/generated_agent/test_logging.py::test_no_raw_pii_in_runner_logs` (roda E2E mockado com PII na imagem; caplog não contém nenhum padrão PII de ARCHITECTURE; contém apenas `params_hash`, `sha256_prefix`) — DbC: Agent + runner logging.Invariant.
- [ ] T031 [P] [DbC] — Teste [AC20] em `tests/generated_agent/test_spec_example.py::test_instruction_under_4kb_cap` (carrega `spec.example.json` + mede `len(spec.instruction.encode("utf-8")) <= 4096`; também testa que spec com `instruction` de 4097 bytes é rejeitado via `transpiler.load_spec`) — DbC: `AgentSpec.instruction.Invariant` (cap 4 KB).

## Implementation (GREEN)

- [ ] T030 — Redigir final `spec.example.json` com `instruction` incorporando plan-then-execute + assembled reformat + trustworthy generation + parameter inspection + error policy (AGENTIC_PATTERNS § 2).
- [ ] T031 — Validar `spec.example.json` via Bloco 1 (`transpiler.load_spec`) e commitar (T022).
- [ ] T032 — Rodar `python -m transpiler docs/fixtures/spec.example.json -o ./generated_agent_out` e inspecionar saída — ajustar templates do Bloco 2 se necessário.
- [ ] T033 — Implementar `security.make_pii_callback(allow_list) -> Callable` (idealmente em `security/` mas pode viver em `generated_agent/callbacks.py` emitido pelo transpilador, decidido em RED).
- [ ] T034 — Garantir que `agent.py.j2` emite `before_model_callback` apontando para o callback acima (AC4).
- [ ] T035 — Implementar runner CLI em `generated_agent/__main__.py` (emitido por template) aceitando `--image`, gerando `image_base64`, invocando o `Runner` ADK, imprimindo tabela final em **ASCII puro** (sem Rich, sem cores — formato literal do AC17) com origem/score/correlation_id em linha complementar. Implementar helper `format_ascii_table(rows, appointment_id, scheduled_for) -> str` puro para snapshot-test (AC9, AC10, AC17).
- [ ] T036 — Configurar `run_config` sem streaming (ADR-0003) no runner.
- [ ] T037 — Adicionar lógica de modo degradado na `instruction` do agente: se `search_exam_code` retornar `None`, chamar `list_exams(limit=20)` e apresentar top candidatos ao usuário pedindo confirmação/correção; marcar exame como não-conclusivo. Zero retry em `E_RAG_NO_MATCH`. Implementar política `E_MCP_TIMEOUT` = 1 retry, 500 ms delay, com `hint` sobre `docker compose ps`. Implementar política `E_API_VALIDATION` = zero retry + mensagem extraindo `<campo>` + `<motivo>` da resposta Pydantic (AC8, AC10, AC14, AC15, AC16).
- [ ] T038 — Emitir logs `event=tool.called` com `params_hash` (sha256 prefix) para todas as chamadas do agente (AC11).
- [ ] T039 — Propagar `X-Correlation-ID` da CLI até o POST na API via `headers` do OpenAPI toolset (AC12).
- [ ] T040 — Criar/ajustar `generated_agent/Dockerfile` (emitido por Bloco 2) para o compose conseguir buildar.

## Refactor

- [ ] T050 — Revisar `instruction` — cortar redundância, manter < 4 KB (NFR).
- [ ] T051 — Se AC2 (paralelismo) falhar devido a serialização do ADK, documentar em evidência + abrir follow-up ADR; **não** modificar a spec sem coordenação.

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0006-generated-agent.md`: saída completa de uma execução E2E com os 5+ logs `event=tool.called` numerados, valor de `correlation_id` destacado, tabela final impressa no terminal.
- [ ] T091 — Anexar screenshot da CLI output (terminal) como PNG ou ASCII art.
- [ ] T092 — Anexar corpo do POST capturado (via sniffer de rede ou log do scheduling-api) mostrando `patient_ref=anon-...`.

## Paralelismo

T004, T010–T022 em paralelo. GREEN: T030/T031 antes de T032 (que roda o transpilador); T033–T039 têm dependências entre si — T033 antes de T034; T035 antes de T036/T038/T039. T040 é o último (consume `agent.py` final).

Dependência externa: Blocos 2, 3, 4, 5 precisam estar em GREEN para os testes de integração rodarem (`docker compose up`). Engenheiros podem escrever RED em paralelo com os outros blocos; GREEN precisa de stack up.
