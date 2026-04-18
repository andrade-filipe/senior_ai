---
id: 0004-scheduling-api
status: proposed
---

## Abordagem técnica

FastAPI + Pydantic v2 + Uvicorn (GUIDELINES § 1), com armazenamento em memória atrás de uma `AppointmentRepository` abstrata. Swagger habilitado em `/docs` (padrão FastAPI). Observabilidade via logs JSON estruturados ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Formato de log"), com middleware que popula `correlation_id` via header `X-Correlation-ID`. Guardrails de body size, caps de payload, timeouts e shape canônico de erro conforme [ADR-0008](../../adr/0008-robust-validation-policy.md).

```
scheduling_api/
├── __main__.py         # uvicorn.run(...)
├── app.py              # FastAPI(app), inclui routers + middleware
├── routes/
│   ├── appointments.py # POST, GET {id}, GET lista
│   └── health.py       # GET /health
├── models.py           # Pydantic (request + response)
├── repository.py       # AppointmentRepository (abstract) + InMemoryAppointmentRepository
├── errors.py           # E_API_NOT_FOUND, E_API_VALIDATION (conforme taxonomia)
├── logging_.py         # middleware de correlation_id + formatter JSON
└── pyproject.toml
```

Endpoints seguem contrato literal em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API". Nenhuma mudança de forma.

- `POST /api/v1/appointments` → cria; status 201.
- `GET /api/v1/appointments/{id}` → lê; 200 ou 404.
- `GET /api/v1/appointments?limit=&offset=` → lista com envelope `{items, total, limit, offset}`.
- `GET /health` → `{"status": "ok"}`.

Middleware `CorrelationIdMiddleware`:
- Lê `X-Correlation-ID`; se ausente, gera `api-<uuid4>[:8]`.
- Propaga via `contextvars.ContextVar` para o logger.
- Inclui header na resposta (eco).

Validação defensiva contra PII (AC9): `PatientRef` é `constr(pattern=r"^anon-[a-z0-9]+$")`. Rejeita qualquer ref que não case; erro `E_API_VALIDATION`. Defesa em profundidade — a camada principal é o agente (Bloco 6).

## Data models

```python
# scheduling_api/models.py
from typing import Annotated, Literal
from pydantic import BaseModel, Field, AwareDatetime
from datetime import datetime

PatientRef = Annotated[str, Field(pattern=r"^anon-[a-z0-9]+$")]

class ExamRef(BaseModel):
    name: str
    code: str

class AppointmentCreate(BaseModel):
    patient_ref: PatientRef
    exams: list[ExamRef] = Field(min_length=1)
    scheduled_for: AwareDatetime
    notes: str | None = None

class Appointment(BaseModel):
    id: str
    status: Literal["scheduled"]
    created_at: AwareDatetime
    patient_ref: PatientRef
    exams: list[ExamRef]
    scheduled_for: AwareDatetime
    notes: str | None

class AppointmentList(BaseModel):
    items: list[Appointment]
    total: int
    limit: int
    offset: int
```

Repository abstrato:

```python
class AppointmentRepository(Protocol):
    def add(self, appt: Appointment) -> None: ...
    def get(self, id_: str) -> Appointment | None: ...
    def list(self, limit: int, offset: int) -> tuple[list[Appointment], int]: ...
```

## Contratos

Contrato HTTP congelado em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API". **Não reescrever aqui.**

O `/openapi.json` emitido será consumido pelo agente (Bloco 6) via ADK OpenAPI toolset — o `openapi_url` vem do `http_tools` no spec (ver `spec.example.json`).

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `Appointment` | `patient_ref` casa `^anon-[a-z0-9]+$`; `scheduled_for` é `AwareDatetime` futura | `id` gerado único; `status="scheduled"`; `created_at` setado pelo servidor; `notes` sem padrões PII (AC17) | `patient_ref` **nunca** contém PII crua (nome, CPF); `scheduled_for > now()` no momento da criação; `notes` ≤ 500 chars (ADR-0008); `exams` ≤ 20 itens | AC9, AC11, AC12, AC13, AC17 | T018 `[DbC]`, T033 `[DbC]`, T034 `[DbC]`, T035 `[DbC]`, T039 `[DbC]` |
| `POST /api/v1/appointments` | body casa `AppointmentCreate` (exams não-vazia, patient_ref no pattern); body ≤ 256 KB (ADR-0008); timeout 10 s | status `201`; resposta casa `Appointment` com `status="scheduled"`; erro emite shape canônico ADR-0008 | `Location` header aponta para `/api/v1/appointments/{id}` recém-criado | AC3, AC10, AC15, AC16 | T012 `[DbC]`, T032 `[DbC]`, T037 `[DbC]`, T038 `[DbC]` |
| `CorrelationIdMiddleware` | request HTTP recebido | `correlation_id` populado em `ContextVar` + ecoado em response header | header `X-Correlation-ID` presente em 100 % das respostas | AC7 | T016 `[DbC]` |
| `GET /api/v1/appointments` | `limit ∈ [1, 100]`, `offset ≥ 0` (ADR-0008) | body casa `AppointmentList` | caps aplicados via Query params | AC14 | T036 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `fastapi` | `^0.110` | Framework HTTP | Flask (rejeitado — sem validação nativa nem OpenAPI auto) |
| `uvicorn[standard]` | `^0.29` | ASGI server | Hypercorn (equivalente; FastAPI default é uvicorn) |
| `pydantic` | `^2.6` | Modelos | — |
| `httpx` | `^0.27` | `AsyncClient` nos testes (GUIDELINES § 4) | `TestClient` sync (rejeitado) |
| `pytest-asyncio` | `^0.23` | Testes async | — |

## Riscos

| Risco | Mitigação |
|---|---|
| `TestClient` síncrono é tentador mas violaria GUIDELINES § 4. | Preâmbulo do RED documenta explicitamente; `qa-engineer` escreve direto com `httpx.AsyncClient`. |
| PII acidentalmente vaza via `notes` em texto livre. | Limitar `notes` a `str | None` com `max_length` razoável no MVP + doc no spec de que `notes` deve vir pré-mascarado (responsabilidade do agente, reforço defesa em profundidade). |
| Armazenamento in-memory some ao restart → E2E flaky. | Bloco 8 sobe compose uma única vez por execução de teste; no MVP aceitável. Interface `AppointmentRepository` permite trocar por `dict` persistente se virar dor. |
| `correlation_id` não propaga se middleware ordem errada. | Adicionar middleware ANTES de qualquer logger instrumentado; teste unitário valida (AC7). |

## Estratégia de validação

- **Same-commit** (ADR-0004): testes junto do código.
- **Unit** em `tests/scheduling_api/test_models.py`: valida `PatientRef` pattern (AC9), `AppointmentCreate` obrigatórios (AC4).
- **Integration** via `httpx.AsyncClient`: AC1–AC7 com instância FastAPI inicializada via fixture.
- **Swagger smoke**: `GET /docs` responde 200 e `GET /openapi.json` é JSON parseável com rota POST (AC2, AC8).
- **Log assertion**: fixture de logger captura; teste valida `event=http.request`, presença de `correlation_id` (AC7).
- **Cobertura**: reportada em evidência; não é gate (≥ 80 % só é gate em `transpiler/` e `security/`).

**Estratégia de validação atualizada (ADR-0008)**:
- **Body size (AC10)**: middleware `BodySizeLimitMiddleware` (Starlette) lê `Content-Length` header antes de consumir body; > 256 KB → resposta 413 com shape canônico.
- **`notes` cap (AC11)**: `Field(max_length=500)` em `AppointmentCreate.notes`.
- **`scheduled_for` futuro (AC12)**: `@model_validator(mode="after")` rejeita se `scheduled_for <= datetime.now(timezone.utc)`.
- **`exams` cap (AC13)**: `Field(max_length=20)` em `AppointmentCreate.exams`.
- **Query caps (AC14)**: `limit: int = Query(10, ge=1, le=100)`, `offset: int = Query(0, ge=0)` nos parâmetros de `GET /api/v1/appointments`.
- **Timeout (AC15)**: `TimeoutMiddleware` envolve o handler em `asyncio.wait_for(..., timeout=10.0)`; `asyncio.TimeoutError` → 504 com `code=E_API_TIMEOUT`.
- **Shape canônico (AC16)**: `@app.exception_handler(RequestValidationError)`, `@app.exception_handler(HTTPException)` e `@app.exception_handler(Exception)` serializam para `{code, message, hint, path, context}` via `format_challenge_error()` helper.
- **PII defensiva em `notes` (AC17)**: `@field_validator("notes")` em `AppointmentCreate` roda regex PII definidos em ARCHITECTURE; match → rejeita com `E_API_VALIDATION`.

## Dependências entre blocos

- **Totalmente independente** de código de outros blocos.
- Em termos de **spec/contrato**: depende apenas de [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API" (frozen).
- **Bloqueia** Bloco 6 (agente precisa do `/openapi.json` para gerar a tool) e Bloco 7 (compose precisa do Dockerfile).
- Habilita **paralelismo** com Blocos 1, 2, 3, 5 — todos podem rodar simultaneamente após checkpoint #1.
