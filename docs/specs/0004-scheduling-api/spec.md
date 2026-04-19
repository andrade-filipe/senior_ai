---
id: 0004-scheduling-api
title: API FastAPI de agendamento com Swagger público
status: implemented
linked_requirements: [R04]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O agente precisa registrar o agendamento do paciente em um serviço HTTP; o avaliador precisa de uma interface Swagger pública para explorar o contrato; o compose precisa de um serviço com healthcheck para orquestrar `depends_on`. Sem este bloco, o fluxo "Ato" do pattern **plan-then-execute** (ver [`ai-context/references/AGENTIC_PATTERNS.md`](../../../ai-context/references/AGENTIC_PATTERNS.md)) não tem destino.

- O que falta hoje? Um serviço FastAPI com endpoints POST/GET, armazenamento in-memory atrás de interface trocável, healthcheck, Swagger habilitado em `/docs`.
- Quem é afetado? Agente gerado (Bloco 6), compose (Bloco 7), avaliador (consome `/docs`), E2E (Bloco 8).
- Por que importa agora? É a **única tool write-action** de todo o sistema ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Classificação das tools") — delimita o raio de explosão de um prompt-injection, então precisa de contrato apertado.

## User stories

- Como **agente**, quero fazer `POST /api/v1/appointments` com o payload canônico e receber `201` com o ID do agendamento criado.
- Como **avaliador**, quero abrir `http://localhost:8000/docs` e explorar a API via Swagger UI.
- Como **devops-engineer**, quero um `GET /health` barato para usar em `HEALTHCHECK` do Dockerfile e `condition: service_healthy` no compose.
- Como **security-engineer**, quero a certeza de que a API **nunca** recebe PII crua — o `patient_ref` é sempre um identificador anônimo (`anon-<hash>`).

## Critérios de aceitação

- [AC1] Dado o serviço rodando em `:8000`, quando `GET /health` é chamado, então retorna `200 OK` com body `{"status": "ok"}`.
- [AC2] Dado o serviço rodando, quando `GET /docs` é acessado, então retorna a Swagger UI com HTTP 200 e inclui operações em `/api/v1/appointments` (POST, GET {id}, GET lista).
- [AC3] Dado um POST `/api/v1/appointments` com body válido conforme [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API", quando processado, então retorna `201 Created` com `id`, `status="scheduled"`, `created_at` (ISO-8601 UTC), `patient_ref`, `exams`, `scheduled_for`.
- [AC4] Dado um POST com `patient_ref` ausente ou `exams` vazio, quando processado, então retorna `422 Unprocessable Entity` com `code=E_API_VALIDATION` e mensagem Pydantic apontando o campo inválido.
- [AC5] Dado um agendamento previamente criado com `id=X`, quando `GET /api/v1/appointments/X` é chamado, então retorna `200 OK` com o recurso; quando o `id` não existe, retorna `404` com `code=E_API_NOT_FOUND`.
- [AC6] Dado N agendamentos criados, quando `GET /api/v1/appointments?limit=10&offset=0` é chamado, então retorna `200 OK` com até 10 items e `total=N` no envelope.
- [AC7] Dado qualquer requisição, quando processada, então um registro de log JSON é emitido com `event=http.request`, `correlation_id` vindo do header `X-Correlation-ID` (gerado se ausente), e `duration_ms`.
- [AC8] Dado o OpenAPI emitido em `/openapi.json`, quando consumido pelo ADK OpenAPI toolset do agente gerado (Bloco 6), então a rota POST é expostas como tool sem erros de parse.
- [AC9] Dado um POST com `patient_ref` contendo formato inesperado (não casando `^anon-[a-z0-9]+$`), quando processado, então retorna `422` — camada defensiva contra PII acidental.
- [AC10] Dado um POST com `Content-Length` > 256 KB, quando processado, então retorna `413 Payload Too Large` com `code=E_API_PAYLOAD_TOO_LARGE` conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md); não chega a Pydantic.
- [AC11] Dado um POST com `notes` > 500 chars, quando processado, então retorna `422` com `code=E_API_VALIDATION` citando campo `notes` e cap.
- [AC12] Dado um POST com `scheduled_for` no passado (antes de `now()` UTC), quando processado, então retorna `422` com `code=E_API_VALIDATION` citando o campo.
- [AC13] Dado um POST com `exams` > 20 itens, quando processado, então retorna `422` com `code=E_API_VALIDATION` citando o cap.
- [AC14] Dado um `GET /api/v1/appointments?limit=101` (ou `offset < 0`), quando processado, então retorna `422` com `code=E_API_VALIDATION` — cap de `limit` é 100, mínimo 1; `offset ≥ 0`.
- [AC15] Dado que o processamento de um endpoint excede 10 segundos, quando inspecionado, então a resposta inclui `code=E_API_TIMEOUT` conforme [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md) (status 504 ou erro estruturado no body).
- [AC16] Dado qualquer resposta de erro 4xx/5xx, quando inspecionada, então o body segue o shape canônico ADR-0008: JSON com `code`, `message`, `hint`, `path`, `context` — nunca o default do FastAPI (`{"detail": ...}`).
- [AC17] Dado o campo `notes` em um `Appointment` criado ou listado, quando inspecionado em qualquer resposta, então nenhum valor casa os padrões de PII (CPF, e-mail, telefone) definidos em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII" — reforço defensivo (a camada primária é o agente, Bloco 6).

## Robustez e guardrails

### Happy Path

Cliente envia `POST /api/v1/appointments` com body de 2 KB (patient_ref `anon-abc123`, 3 exams, `scheduled_for` futuro, sem notes ou notes < 500 chars) → retorna `201 Created` em < 50 ms com `X-Correlation-ID` ecoado.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| Body > 256 KB | rejeitar antes de Pydantic | `E_API_PAYLOAD_TOO_LARGE` (413) | AC10 |
| `notes` > 500 chars | rejeitar via Pydantic | `E_API_VALIDATION` (422) | AC11 |
| `scheduled_for` no passado | rejeitar via `model_validator` | `E_API_VALIDATION` (422) | AC12 |
| `exams` > 20 itens | rejeitar via `Field(max_length=20)` | `E_API_VALIDATION` (422) | AC13 |
| `limit` > 100 ou `offset` < 0 | rejeitar via Query params | `E_API_VALIDATION` (422) | AC14 |
| Endpoint > 10 s | timeout hard | `E_API_TIMEOUT` (504) | AC15 |
| Erro qualquer | shape canônico ADR-0008 | — | AC16 |
| `notes` com padrão PII | rejeitar ou logar alerta | `E_API_VALIDATION` | AC17 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| Body do request | 256 KB | `E_API_PAYLOAD_TOO_LARGE` | AC10 |
| `notes` (chars) | 500 | `E_API_VALIDATION` | AC11 |
| `exams[]` | 20 itens | `E_API_VALIDATION` | AC13 |
| `limit` (query) | 1–100 | `E_API_VALIDATION` | AC14 |
| Endpoint (timeout) | 10 s | `E_API_TIMEOUT` | AC15 |

### Security & threats

- **Ameaça**: cliente envia POST de 100 MB com `notes` gigante e derruba o uvicorn.
  **Mitigação**: cap de 256 KB no body via middleware antes de Pydantic (AC10).
- **Ameaça**: `notes` texto livre vira vetor de PII (paciente escreve "meu CPF é X") e passa direto para logs ou persistência.
  **Mitigação**: cap de 500 chars + validador defensivo em `Appointment` que rejeita se casar padrões PII (AC11, AC17); fonte primária de mascaramento é o agente (Bloco 6).
- **Ameaça**: `scheduled_for` no passado pode ser usado para popular agenda com "fatos consumados" falsos.
  **Mitigação**: `model_validator` rejeita `scheduled_for <= now()` (AC12).
- **Ameaça**: shape de erro default do FastAPI (`{"detail": ...}`) dificulta rastreabilidade entre componentes.
  **Mitigação**: exception handler customizado em `app.py` normaliza todas as respostas de erro para shape ADR-0008 (AC16).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC3 | `POST /api/v1/appointments` | Post |
| AC9 | `Appointment` | Invariant (PII-ref pattern) |
| AC7 | `CorrelationIdMiddleware` | Invariant |
| AC10 | `BodySizeLimitMiddleware` | Pre (ADR-0008 body cap) |
| AC11, AC12, AC13 | `AppointmentCreate` | Invariant (caps + `scheduled_for` futuro) |
| AC14 | `GET /api/v1/appointments` | Pre (query caps) |
| AC15 | `TimeoutMiddleware` | Post (ADR-0008 timeouts) |
| AC16 | `app.py` exception handler | Post (shape canônico) |
| AC17 | `Appointment` | Invariant (PII defensiva) |

## Requisitos não-funcionais

- **Tecnologia**: FastAPI + Pydantic v2 + Uvicorn (GUIDELINES § 1).
- **Armazenamento**: in-memory `dict[str, Appointment]` atrás de interface `AppointmentRepository`; trocável por classe mock nos testes.
- **Idempotência**: GETs são seguros para retry; o POST **não** é idempotente no MVP (aceitável, write-action única).
- **Observabilidade**: logs JSON com `correlation_id` propagado ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Formato de log").
- **Healthcheck**: `/health` responde em < 10 ms sem tocar estado.
- **Latência**: p95 < 100 ms para todos os endpoints em dev local (inspeção manual).
- **Tests**: `httpx.AsyncClient` (GUIDELINES § 4), **não** `TestClient` sync.

## Clarifications

*(nenhuma — contrato totalmente definido em `docs/ARCHITECTURE.md`.)*

## Fora de escopo

- Persistência durável (Postgres, SQLite). In-memory é suficiente para o MVP — interface documentada permite troca futura.
- Autenticação / autorização (rede interna no compose; API exposta no host apenas para o avaliador).
- Atualização ou cancelamento de agendamento (nenhum requisito pede).
- Rate limiting.
- Idempotency keys.
