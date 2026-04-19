# Evidência — Bloco 0008 · E2E + Evidências Consolidadas + Transparência

- **Spec**: [`docs/specs/0008-e2e-evidence-transparency/spec.md`](../specs/0008-e2e-evidence-transparency/spec.md)
- **Status**: `done` — fechado em 2026-04-19.
- **Ambiente**: Windows 11, Docker Desktop 29.3.1, `uv 0.11.7`, Python `3.12.13`.

## Resumo

- Suite E2E CI: 10 passed, 2 skipped (OCR/RAG exec cross-container — ver seção Desvios).
- Audit PII: `audit_logs_pii.py` relatou `{"matches": 0, "samples": []}` em todos os logs.
- Shape canônico de erro validado na scheduling-api (3 cenários) e transpiler CLI (2 cenários).
- Fixtures verificadas: `sample_medical_order.png` e `spec.example.json` presentes e válidos.

## AC1b — Roteiro E2E Manual Completo (com Gemini real)

> Este roteiro é executado localmente pelo avaliador. Requer `GOOGLE_API_KEY` válida.

```bash
# 1. Clonar e configurar
git clone <repo-url>
cd Senior_IA
cp .env.example .env
# Editar .env: preencher GOOGLE_API_KEY=AIza...

# 2. Subir stack (3 serviços de infraestrutura)
docker compose up -d ocr-mcp rag-mcp scheduling-api

# 3. Aguardar healthchecks (até 60s)
# Verificar: docker compose ps

# 4. Executar agente com imagem de exemplo
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png

# 5. Verificar resultado esperado:
# - Saída tabela ASCII no terminal
# - POST criado na API: http://localhost:8000/api/v1/appointments
# - Log com correlation_id visível em: docker compose logs scheduling-api

# 6. Teardown
docker compose down -v
```

Saída esperada do agente (tabela ASCII + ID de agendamento):
```
+-----+--------------------+---------+-------+
| #   | Exame              | Codigo  | Score |
+-----+--------------------+---------+-------+
| 1   | Hemograma Completo | HMG-001 | 0.98  |
| 2   | Glicemia de Jejum  | GLJ-002 | 0.96  |
| 3   | Colesterol Total   | COL-003 | 0.94  |
+-----+--------------------+---------+-------+
Appointment ID: apt-abc123  |  Scheduled: 2026-05-01T09:00:00
```

## Comandos reproduzíveis (suite E2E CI)

```bash
# Passo 1 — testes sem Docker (fixtures + PII audit self-test + transpiler CLI)
cd scheduling_api
uv run pytest ../tests/infra/test_fixtures.py \
  ../tests/e2e/test_no_pii_in_logs.py::TestAuditScriptSelfTest \
  ../tests/e2e/test_error_shape.py::TestTranspilerCliErrorShape \
  -v --no-cov

# Passo 2 — subir stack (imagens já construídas)
export DOCKER_BIN="/c/Program Files/Docker/Docker/resources/bin/docker.exe"
"$DOCKER_BIN" compose up -d ocr-mcp rag-mcp scheduling-api

# Passo 3 — aguardar saúde
# (wait_for_healthy sondando http://localhost:8000/health)

# Passo 4 — suite E2E completa
uv run pytest ../tests/e2e -m e2e_ci -v --no-cov

# Passo 5 — auditoria PII nos logs
"$DOCKER_BIN" logs senior_ia-scheduling-api-1 > /tmp/svc_logs.log 2>&1
"$DOCKER_BIN" logs senior_ia-ocr-mcp-1 >> /tmp/svc_logs.log 2>&1
"$DOCKER_BIN" logs senior_ia-rag-mcp-1 >> /tmp/svc_logs.log 2>&1
uv run python ../scripts/audit_logs_pii.py --log-file /tmp/svc_logs.log

# Passo 6 — teardown
"$DOCKER_BIN" compose down -v
```

## Saída do pytest E2E CI (execução real — 2026-04-19)

```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
collected 19 items / 7 deselected / 12 selected

tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_compose_up_healthchecks PASSED
tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_scheduling_api_openapi_reachable PASSED
tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_ocr_mcp_sse_reachable PASSED
tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_rag_mcp_sse_reachable PASSED
tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_correlation_id_visible_in_api_log PASSED
tests/e2e/test_ci_flow.py::TestComposeHealthchecksAndIntegration::test_patient_ref_is_anonymized_in_api_state PASSED
tests/e2e/test_error_shape.py::TestSchedulingApiErrorShape::test_payload_too_large_returns_canonical_shape PASSED
tests/e2e/test_error_shape.py::TestSchedulingApiErrorShape::test_validation_error_returns_canonical_shape PASSED
tests/e2e/test_error_shape.py::TestSchedulingApiErrorShape::test_not_found_returns_canonical_shape PASSED
tests/e2e/test_error_shape.py::TestOcrMcpErrorShape::test_ocr_oversized_image_via_exec SKIPPED
tests/e2e/test_error_shape.py::TestRagMcpErrorShape::test_rag_query_too_large_via_exec SKIPPED
tests/e2e/test_no_pii_in_logs.py::TestNoPiiInComposeLogs::test_audit_logs_pii_zero_matches PASSED

================= 10 passed, 2 skipped, 7 deselected in 2.58s =================
```

## Log trimado — correlation_id destacado (AC6, AC2)

Logs capturados após `POST /api/v1/appointments` com `X-Correlation-ID: **e2e-log-capture-test**`:

```json
{"ts": "2026-04-19T17:20:12.303Z", "level": "INFO", "service": "scheduling-api", "correlation_id": "api-19e09eb0", "event": "http.request", "method": "GET", "path": "/health", "status_code": 200, "duration_ms": 0.81}
{"ts": "2026-04-19T17:20:28.800Z", "level": "INFO", "service": "scheduling-api", "correlation_id": "**e2e-log-capture-test**", "event": "http.request", "method": "POST", "path": "/api/v1/appointments", "status_code": 201, "duration_ms": 1.99}
{"ts": "2026-04-19T17:20:08.408Z", "level": "INFO", "service": "ocr-mcp", "event": "server.starting", "extra": {"port": 8001, "transport": "sse"}}
{"ts": "2026-04-19T17:20:08.429Z", "level": "INFO", "service": "rag-mcp", "event": "catalog.loading", "extra": {"path": "/usr/local/lib/python3.12/site-packages/rag_mcp/data/exams.csv"}}
{"ts": "2026-04-19T17:20:08.431Z", "level": "INFO", "service": "rag-mcp", "event": "catalog.loaded", "extra": {"entry_count": 118, "choice_count": 416}}
{"ts": "2026-04-19T17:20:08.431Z", "level": "INFO", "service": "rag-mcp", "event": "server.starting", "extra": {"port": 8002, "transport": "sse"}}
```

## Saída auditoria PII (AC14)

```bash
$ uv run python scripts/audit_logs_pii.py --log-file /tmp/svc_logs.log
{"matches": 0, "samples": []}
# exit code: 0 — logs limpos
```

## Desvios do spec

| Desvio | Motivo | Impacto |
|---|---|---|
| `TestOcrMcpErrorShape` → SKIPPED | `docker compose exec` usa caminhos Unix-style não acessíveis via `subprocess.run()` no Windows. OCR MCP não publica porta ao host (AC7). Error shape verificado via `ocr_mcp/tests/test_guards.py` (unit). | Baixo — unit tests cobrem o comportamento; skip documentado com razão clara. |
| `TestRagMcpErrorShape` → SKIPPED | Mesma razão. RAG MCP unit tests em `rag_mcp/tests/` cobrem E_RAG_QUERY_TOO_LARGE. | Baixo — mesma justificativa. |
| Cobertura `security/` = 76.62 % | Paths de inicialização spaCy/multiprocessing não exercitados nos unit tests com mock. | Documentado em `docs/EVIDENCE/0005-pii-guard.md`. Floor de 80 % não atingido; ADR-0004 admite "best effort, justified if lower" para módulos sem caminho de integração viável. |

## Mapeamento AC → evidência/teste

| AC | Cobertura | Local |
|---|---|---|
| AC1a — E2E CI sem Gemini | PASSED (10 testes) | `tests/e2e/test_ci_flow.py` |
| AC1b — E2E manual com Gemini | Roteiro neste arquivo | Seção "AC1b" acima |
| AC2 — correlation_id no log | PASSED | `test_correlation_id_visible_in_api_log` |
| AC3 — patient_ref mascarado | PASSED | `test_patient_ref_is_anonymized_in_api_state` |
| AC4 — evidência por bloco | PRESENTE | `docs/EVIDENCE/0001..0008-*.md` |
| AC5 — Swagger screenshot | Link em 0004 | `docs/EVIDENCE/0004-scheduling-api.md` |
| AC6 — log E2E com cid | PRESENTE | Seção "Log trimado" acima |
| AC7 — fixtures presentes | PASSED | `tests/infra/test_fixtures.py` |
| AC8 — spec.example.json valida | PASSED | `test_spec_example_passes_transpiler_load_spec` |
| AC14 — no-PII-in-logs | PASSED + audit exit 0 | `test_audit_logs_pii_zero_matches` |
| AC15 — shape canônico de erro | PASSED (5) + SKIPPED (2) | `tests/e2e/test_error_shape.py` |
