---
id: 0008-e2e-evidence-transparency
status: todo
---

## Setup

- [ ] T001 — Criar `tests/e2e/__init__.py` e `tests/e2e/conftest.py` com helper `wait_for_healthy(url, timeout)` e fixture `compose_stack` que sobe/derruba via `docker compose`.
- [ ] T002 — Adicionar dois markers em `pyproject.toml` da raiz (ou `pytest.ini`): `markers = ["e2e_ci: compose + healthchecks + unit/integration sem Gemini real", "e2e_full: fluxo manual com Gemini real"]`. Documentar no README qual é rodado em CI e qual é manual.
- [ ] T003 [P] — Criar `docs/EVIDENCE/` (se não existir) e um template `docs/EVIDENCE/TEMPLATE.md` com as seções fixas (comandos / log / cobertura / screenshots).
- [ ] T004 [P] — Criar `docs/fixtures/` (coordenado com Bloco 6 T001–T002) — se Bloco 6 já criou, verificar presença.

## Tests (same-commit — E2E + smoke de fixtures)

- [ ] T010a — Escrever teste [AC1a] em `tests/e2e/test_ci_flow.py::test_compose_healthchecks_and_integration_suite` — marker `@pytest.mark.e2e_ci`; sobe compose; aguarda healthchecks; roda suítes unit + integration dos serviços sem chamar Gemini real.
- [ ] T010b — Roteiro manual (prose, não script) para [AC1b] em `docs/EVIDENCE/0008-e2e-evidence-transparency.md`: passo-a-passo que o avaliador executa para rodar o E2E completo com Gemini real; captura de log + print da tabela ASCII final anexada como evidência.
- [ ] T011 — Escrever teste [AC2] em `tests/e2e/test_full_flow.py::test_correlation_id_visible_in_api_log` (parseia logs do container).
- [ ] T012 — Escrever teste [AC3] em `tests/e2e/test_full_flow.py::test_patient_ref_is_anonymized_in_api_state`.
- [ ] T013 [P] — Escrever teste [AC7] em `tests/infra/test_fixtures.py::test_sample_image_and_spec_present`.
- [ ] T014 [P] — Escrever teste [AC8] em `tests/infra/test_fixtures.py::test_spec_example_passes_transpiler_load_spec`.
- [ ] T015 — Escrever teste [AC14] em `tests/e2e/test_no_pii_in_logs.py::test_audit_logs_pii_zero_matches` (após E2E CI, invoca `scripts/audit_logs_pii.py` sobre logs coletados; exit = 0 e `matches_count == 0`). Implementar `scripts/audit_logs_pii.py` com regex PII de ARCHITECTURE § "Lista definitiva de entidades PII".
- [ ] T016 — Escrever teste [AC15] em `tests/e2e/test_error_shape.py::test_canonical_error_shape_across_components` (induz erro em transpiler via spec inválido; em OCR via image_base64 > 5 MB; em RAG via query > 500 chars; em API via body > 256 KB; valida que cada erro serializa `{code, message, hint, path, context}`).

## Implementation (GREEN)

### E2E

- [ ] T020 — Implementar `wait_for_healthy` em `tests/e2e/conftest.py` com polling `httpx.get("http://localhost:8000/health")` e timeout 60s.
- [ ] T021 — Implementar `test_agent_creates_appointment_via_compose`: `docker compose up -d` subset + `docker compose run --rm generated-agent ...` + asserts (AC1).
- [ ] T022 — Implementar parsing de logs via `docker compose logs scheduling-api` e asserção de `correlation_id` (AC2).
- [ ] T023 — Implementar asserção de `patient_ref` pattern via `GET /api/v1/appointments` (AC3).
- [ ] T024 — Garantir teardown idempotente com `docker compose down -v` em `finally` / fixture teardown.

### Evidências por bloco

- [ ] T030 [P] — Preencher `docs/EVIDENCE/0001-agentspec-schema.md` com evidência coletada no T090 do Bloco 1.
- [ ] T031 [P] — Preencher `docs/EVIDENCE/0002-transpiler-mvp.md` com evidência dos T090/T091 do Bloco 2.
- [ ] T032 [P] — Preencher `docs/EVIDENCE/0003-mcp-ocr-rag.md`.
- [ ] T033 [P] — Preencher `docs/EVIDENCE/0004-scheduling-api.md` incluindo screenshot da Swagger UI (AC5).
- [ ] T034 [P] — Preencher `docs/EVIDENCE/0005-pii-guard.md`.
- [ ] T035 [P] — Preencher `docs/EVIDENCE/0006-generated-agent.md` incluindo screenshot/ASCII da CLI output.
- [ ] T036 [P] — Preencher `docs/EVIDENCE/0007-docker-compose.md`.
- [ ] T037 — Preencher `docs/EVIDENCE/0008-e2e-evidence-transparency.md` com log completo de uma execução E2E bem-sucedida + `correlation_id` destacado (AC6).

### README final

- [ ] T040 — Criar/atualizar `README.md` na raiz com: badge CI, diagrama de arquitetura (inline ou link para ARCHITECTURE.md), stack (AC9).
- [ ] T041 — Adicionar seção Quickstart com três comandos (`cp .env.example .env`, `docker compose up -d`, `docker compose run generated-agent --image ...`) (AC9).
- [ ] T042 — Adicionar seção "Estrutura do repositório" com cada diretório em 1 linha (AC11).
- [ ] T043 — Adicionar seção "Transparência e Uso de IA" (R12) com: abordagem SDD+TDD, subagentes, referências (link para `ai-context/LINKS.md` + `DESIGN_AUDIT.md` + `AGENTIC_PATTERNS.md`), estratégia de orquestração (AC10).
- [ ] T044 — Adicionar links para `docs/EVIDENCE/`, `docs/specs/`, `docs/adr/`, `docs/ARCHITECTURE.md`, `docs/REQUIREMENTS.md`.

### Status final

- [ ] T050 — Atualizar `ai-context/STATUS.md` marcando todos os 8 blocos como `done` + histórico de checkpoints (AC12).
- [ ] T051 — Atualizar `docs/specs/0001..0007/spec.md` front-matter para `status: implemented` (AC13).

## Refactor

- [ ] T060 — Cap `README.md` em 500 linhas; linkar em vez de duplicar.
- [ ] T061 — Verificar que todos os links em `README.md` resolvem (script simples ou inspeção manual).

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0008-e2e-evidence-transparency.md`: saída de `pytest -m e2e` com timestamp, dump de `docker compose logs` com `correlation_id` coloridos, link para o commit de cada spec `implemented`.

## Paralelismo

`[P]`: T003, T004, T013, T014, T030–T036 amplamente paralelo (arquivos distintos). E2E (T010–T012, T020–T024) é inerentemente sequencial. README (T040–T044) pode ser feito em paralelo com evidências (T030–T037).

Dependência cross-bloco: T030–T036 dependem dos evidence steps (T090+) dos blocos correspondentes. T040–T044 é possível em paralelo com tudo. T050/T051 é o último passo de fechamento — único gate sequencial.
