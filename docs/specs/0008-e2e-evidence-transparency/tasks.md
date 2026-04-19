---
id: 0008-e2e-evidence-transparency
status: todo
---

## Setup

- [x] T001 — Criar `tests/e2e/__init__.py` e `tests/e2e/conftest.py` com helper `wait_for_healthy(url, timeout)` e fixture `compose_stack` que sobe/derruba via `docker compose`.
- [x] T002 — Adicionar marcadores `e2e_ci` e `e2e_full` em `scheduling_api/pyproject.toml[tool.pytest.ini_options].markers` (anchor canônico); `tests/e2e/conftest.py` também registra para descoberta autônoma.
- [x] T003 [P] — `docs/EVIDENCE/` já existia; arquivos 0002/0004/0005/0007/0008 criados nesta wave.
- [ ] T004 [P] — Criar `docs/fixtures/` (coordenado com Bloco 6 T001–T002) — se Bloco 6 já criou, verificar presença.

## Tests (same-commit — E2E + smoke de fixtures)

- [x] T010a — Escrever teste [AC1a] em `tests/e2e/test_ci_flow.py` — marker `@pytest.mark.e2e_ci`; classe `TestComposeHealthchecksAndIntegration`; testes de health, openapi, MCP reachability.
- [x] T010b — Roteiro manual (prose) para [AC1b] em `docs/EVIDENCE/0008-e2e-evidence-transparency.md`: seção "AC1b — Roteiro E2E Manual Completo".
- [x] T011 — Escrever teste [AC2] em `tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_correlation_id_visible_in_api_log`.
- [x] T012 — Escrever teste [AC3] em `tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_patient_ref_is_anonymized_in_api_state`.
- [x] T013 [P] — Escrever teste [AC7] em `tests/infra/test_fixtures.py::TestFixtureFilesPresent::test_sample_image_and_spec_present`.
- [x] T014 [P] — Escrever teste [AC8] em `tests/infra/test_fixtures.py::TestSpecExampleSchemaValidation::test_spec_example_passes_transpiler_load_spec`.
- [x] T015 — Escrever teste [AC14] em `tests/e2e/test_no_pii_in_logs.py` + implementar `scripts/audit_logs_pii.py` com regex PII de ARCHITECTURE.
- [x] T016 — Escrever teste [AC15] em `tests/e2e/test_error_shape.py` (API: 3 cenários PASSED; OCR/RAG: 2 SKIPPED com razão documentada; transpiler CLI: 2 PASSED).

## Implementation (GREEN)

### E2E

- [x] T020 — Implementar `wait_for_healthy` em `tests/e2e/conftest.py` com polling `httpx.get` e timeout 60s.
- [ ] T021 — `test_agent_creates_appointment_via_compose` (AC1b — manual com Gemini; roteiro em evidence file).
- [x] T022 — Parsing de logs via `collect_compose_logs("scheduling-api")` e asserção de `correlation_id` (AC2) — PASSED.
- [x] T023 — Asserção de `patient_ref` pattern via `GET /api/v1/appointments` (AC3) — PASSED.
- [x] T024 — Teardown idempotente com `docker compose down -v` em `finally` no `compose_stack` fixture.

### Evidências por bloco

- [x] T030 [P] — `docs/EVIDENCE/0001-agentspec-schema.md` já existia com conteúdo real do Bloco 1.
- [x] T031 [P] — `docs/EVIDENCE/0002-transpiler-mvp.md` criado nesta wave (Wave 5a).
- [x] T032 [P] — `docs/EVIDENCE/0003-mcp-ocr-rag.md` já existia.
- [x] T033 [P] — `docs/EVIDENCE/0004-scheduling-api.md` criado nesta wave com coverage + log + Swagger ref.
- [x] T034 [P] — `docs/EVIDENCE/0005-pii-guard.md` criado nesta wave.
- [x] T035 [P] — `docs/EVIDENCE/0006-generated-agent.md` já existia (aguarda E2E manual completo).
- [x] T036 [P] — `docs/EVIDENCE/0007-docker-compose.md` criado nesta wave.
- [x] T037 — `docs/EVIDENCE/0008-e2e-evidence-transparency.md` criado com log real E2E + correlation_id + roteiro AC1b.

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
