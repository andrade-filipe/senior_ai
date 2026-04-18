---
id: 0004-scheduling-api
status: todo
---

## Setup

- [ ] T001 — Criar `scheduling_api/pyproject.toml` com `fastapi^0.110`, `uvicorn[standard]^0.29`, `pydantic^2.6`, `httpx^0.27`, `pytest-asyncio^0.23`.
- [ ] T002 — Criar estrutura `scheduling_api/` com `__main__.py`, `app.py`, `models.py`, `repository.py`, `errors.py`, `logging_.py`, `routes/appointments.py`, `routes/health.py` (placeholders).
- [ ] T003 [P] — Criar `tests/scheduling_api/conftest.py` com fixture `async_client` (`httpx.AsyncClient(transport=ASGITransport(app=app))`).
- [ ] T004 [P] — Criar fixture `sample_create_payload` em `conftest.py` com `patient_ref="anon-abc123"`, exams válidos, `scheduled_for` ISO.

## Tests (same-commit)

- [ ] T010 [P] — Teste [AC1] em `tests/scheduling_api/test_health.py::test_health_returns_ok`.
- [ ] T011 [P] — Teste [AC2] em `tests/scheduling_api/test_swagger.py::test_docs_ui_available` + `test_openapi_has_post_route`.
- [ ] T012 [P] [DbC] — Teste [AC3] em `tests/scheduling_api/test_appointments.py::test_create_returns_201_with_canonical_shape` — DbC: `POST /api/v1/appointments.Post`.
- [ ] T013 [P] — Teste [AC4] em `tests/scheduling_api/test_appointments.py::test_invalid_body_returns_422_with_e_api_validation`.
- [ ] T014 [P] — Teste [AC5] em `tests/scheduling_api/test_appointments.py::test_get_by_id_200_and_404`.
- [ ] T015 [P] — Teste [AC6] em `tests/scheduling_api/test_appointments.py::test_list_pagination`.
- [ ] T016 [P] [DbC] — Teste [AC7] em `tests/scheduling_api/test_logging.py::test_correlation_id_propagated_and_logged` — DbC: `CorrelationIdMiddleware.Invariant` (`X-Correlation-ID` presente em 100% das respostas).
- [ ] T017 [P] — Teste [AC8] em `tests/scheduling_api/test_openapi.py::test_openapi_json_parseable`.
- [ ] T018 [P] [DbC] — Teste [AC9] em `tests/scheduling_api/test_appointments.py::test_non_anon_patient_ref_rejected_422` — DbC: `Appointment.Invariant` (`patient_ref` pattern; PII-zero).
- [ ] T029 [P] [DbC] — Teste [AC10] em `tests/scheduling_api/test_guards.py::test_body_size_limit_413` (POST com body de 300 KB → 413 com `code=E_API_PAYLOAD_TOO_LARGE`; Pydantic nunca executado — assert middleware-level) — DbC: `BodySizeLimitMiddleware.Pre`.
- [ ] T033 [P] [DbC] — Teste [AC11] em `tests/scheduling_api/test_appointments.py::test_notes_over_500_chars_rejected` (POST com `notes` de 501 chars → 422 citando campo `notes` e cap) — DbC: `AppointmentCreate.Invariant` (caps).
- [ ] T034 [P] [DbC] — Teste [AC12] em `tests/scheduling_api/test_appointments.py::test_scheduled_for_in_past_rejected` (POST com `scheduled_for=<ontem>` → 422 citando `scheduled_for`) — DbC: `AppointmentCreate.Invariant` (futuro).
- [ ] T035 [P] [DbC] — Teste [AC13] em `tests/scheduling_api/test_appointments.py::test_exams_over_20_items_rejected` (POST com 21 exams → 422 citando cap) — DbC: `AppointmentCreate.Invariant` (cap exams).
- [ ] T036 [P] [DbC] — Teste [AC14] em `tests/scheduling_api/test_appointments.py::test_pagination_caps` (`?limit=101` → 422; `?limit=0` → 422; `?offset=-1` → 422) — DbC: `GET /api/v1/appointments.Pre`.
- [ ] T037 [P] [DbC] — Teste [AC15] em `tests/scheduling_api/test_guards.py::test_endpoint_timeout_504` (monkey-patch de um handler com `asyncio.sleep(11)` → resposta com `code=E_API_TIMEOUT`) — DbC: `POST /api/v1/appointments.Post` (timeout).
- [ ] T038 [P] [DbC] — Teste [AC16] em `tests/scheduling_api/test_errors.py::test_error_response_shape_canonical` (provoca 422 via body inválido + 404 via `GET /api/v1/appointments/inexistente` → body tem todas as chaves `code`, `message`, `hint`, `path`, `context`; nunca `detail`) — DbC: `app.py exception handler.Post`.
- [ ] T039 [P] [DbC] — Teste [AC17] em `tests/scheduling_api/test_appointments.py::test_notes_with_pii_rejected` (POST com `notes="meu CPF é 111.444.777-35"` → 422 com `code=E_API_VALIDATION` citando padrão PII detectado) — DbC: `Appointment.Invariant` (PII defensiva).

## Implementation (GREEN)

- [ ] T020 — Implementar `scheduling_api/errors.py` com `ChallengeError` base + `E_API_NOT_FOUND`, `E_API_VALIDATION`.
- [ ] T021 — Implementar `scheduling_api/models.py`: `PatientRef` com pattern, `ExamRef`, `AppointmentCreate`, `Appointment`, `AppointmentList` conforme [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API".
- [ ] T022 — Implementar `scheduling_api/repository.py` com `AppointmentRepository` Protocol + `InMemoryAppointmentRepository` (dict).
- [ ] T023 — Implementar `scheduling_api/logging_.py`: JSON formatter + `CorrelationIdMiddleware` (lê `X-Correlation-ID`, gera se ausente, popula `contextvars.ContextVar`).
- [ ] T024 — Implementar `scheduling_api/routes/health.py` com `@router.get("/health")` (AC1).
- [ ] T025 — Implementar `scheduling_api/routes/appointments.py` com POST, GET {id}, GET lista (AC3–AC6, AC9).
- [ ] T026 — Implementar `scheduling_api/app.py` montando FastAPI + middleware + routers + exception handlers (422 custom com `code=E_API_VALIDATION`, 404 com `code=E_API_NOT_FOUND`).
- [ ] T027 — Implementar `scheduling_api/__main__.py` com `uvicorn.run("scheduling_api.app:app", host="0.0.0.0", port=8000)`.
- [ ] T028 — Criar `scheduling_api/Dockerfile` seguindo template do Bloco 7 plan (AC5 deste bloco + Blocos 7 AC1–AC5).

## Refactor

- [ ] T030 — Extrair gerador de ID (`generate_appointment_id() -> str`) em helper dedicado caso inline em T022.
- [ ] T031 — Adicionar `response_model` + `status_code` em todos os decorators para OpenAPI mais rico (AC2, AC8).
- [ ] T032 — Rodar `uv run ruff check .` e `uv run mypy scheduling_api/` (non-strict).

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0004-scheduling-api.md`: `uv run pytest tests/scheduling_api/`, screenshot da Swagger UI em `/docs` (AC5 do Bloco 8), exemplo de log JSON com `correlation_id`.
- [ ] T091 — Anexar `curl -i -X POST http://localhost:8000/api/v1/appointments ...` com resposta 201.

## Paralelismo

`[P]`: T003, T004, T010–T018 (todos tests isolados). GREEN: T020–T023 podem rodar em paralelo; T024 e T025 dependem de T020–T023; T026 integra; T027 e T028 finais.
