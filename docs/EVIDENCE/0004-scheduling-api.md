# Evidência — Bloco 0004 · Scheduling API (FastAPI)

- **Spec**: [`docs/specs/0004-scheduling-api/spec.md`](../specs/0004-scheduling-api/spec.md)
- **Status**: `done` — fechado em 2026-04-18.
- **Ambiente**: Windows 11, `uv 0.11.7`, Python `3.12.13`.
- **Pyproject**: `scheduling_api/pyproject.toml` (per-service, ADR-0005).

## Resumo

- 86 testes em `tests/scheduling_api/` + `tests/infra/` cobrem AC1–AC17.
- Cobertura medida: **95 %** (limite ADR-0004: 80 %).
- Middleware stack: `TimeoutMiddleware` → `BodySizeLimitMiddleware` → `CorrelationIdMiddleware`.
- Todos os erros usam shape canônico ADR-0008 (`{error: {code, message, hint, path, context}, correlation_id}`).
- Nunca usa `{"detail": ...}` padrão do FastAPI.

## Comandos reproduzíveis

```bash
cd scheduling_api
uv sync
uv run pytest --cov=scheduling_api --cov-report=term-missing -v
```

## Cobertura

```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
scheduling_api/__init__.py                  0      0   100%
scheduling_api/__main__.py                  3      3     0%   (not exercised in unit test)
scheduling_api/app.py                      76      8    89%
scheduling_api/errors.py                   20      0   100%
scheduling_api/logging_.py                 46      0   100%
scheduling_api/models.py                   50      0   100%
scheduling_api/repository.py               23      0   100%
scheduling_api/routes/__init__.py           0      0   100%
scheduling_api/routes/appointments.py      29      1    97%
scheduling_api/routes/health.py             6      0   100%
---------------------------------------------------------------------
TOTAL                                     253     12    95%
Required coverage of 80% reached. Total: 95%
```

## Log JSON capturado (docker compose run)

Exemplos de linhas emitidas pela API em produção (sem PII):

```json
{"ts": "2026-04-19T17:20:12.303Z", "level": "INFO", "service": "scheduling-api", "correlation_id": "api-19e09eb0", "event": "http.request", "method": "GET", "path": "/health", "status_code": 200, "duration_ms": 0.81}
{"ts": "2026-04-19T17:20:28.800Z", "level": "INFO", "service": "scheduling-api", "correlation_id": "**e2e-log-capture-test**", "event": "http.request", "method": "POST", "path": "/api/v1/appointments", "status_code": 201, "duration_ms": 1.99}
```

O campo `correlation_id` propagado do header `X-Correlation-ID` aparece intacto.

## Swagger UI

A Swagger UI fica disponível em `http://localhost:8000/docs` quando a API está rodando.

Para acessar:
```bash
docker compose up -d scheduling-api
# Aguardar healthcheck; abrir http://localhost:8000/docs no navegador
```

Endpoints documentados:
- `POST /api/v1/appointments` — cria agendamento (body `AppointmentCreate`)
- `GET /api/v1/appointments/{id}` — lê por ID
- `GET /api/v1/appointments` — lista paginada
- `GET /health` — healthcheck

Screenshot: `docs/EVIDENCE/swagger-ui.png` (capturar manualmente via
`http://localhost:8000/docs` após `docker compose up -d scheduling-api`).

## OpenAPI JSON (trecho)

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Scheduling API",
    "version": "1.0.0",
    "description": "API de agendamento de exames..."
  },
  "paths": {
    "/api/v1/appointments": {
      "post": { "summary": "Criar agendamento", "operationId": "create_appointment_..." },
      "get":  { "summary": "Listar agendamentos", "operationId": "list_appointments_..." }
    },
    "/api/v1/appointments/{id}": {
      "get": { "summary": "Buscar agendamento por ID" }
    },
    "/health": { "get": { "summary": "Healthcheck" } }
  }
}
```

## Mapeamento AC → teste

| AC | Cenário | Arquivo |
|---|---|---|
| AC1 — `GET /health` 200 | `test_health_ok` | `test_health.py` |
| AC3 — POST 201 | `test_create_appointment_success` | `test_appointments.py` |
| AC5 — GET /{id} 200 | `test_get_appointment_by_id` | `test_appointments.py` |
| AC9 — patient_ref pattern | `test_patient_ref_pattern_enforced` | `test_guards.py` |
| AC10 — body > 256 KB → 413 | `test_payload_too_large` | `test_guards.py` |
| AC15 — timeout 504 | `test_request_timeout` | `test_guards.py` |
| AC16 — shape canônico | `test_error_shape_*` | `test_errors.py` |
| AC17 — PII em notes rejeitado | `test_notes_pii_rejected` | `test_guards.py` |
