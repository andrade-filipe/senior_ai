# Tutorial 04 — Scheduling API (FastAPI)

## 1. Objetivo

Ao final deste tutorial você será capaz de:

- Subir a API de agendamento localmente com Docker Compose.
- Explorar o contrato interativamente via Swagger UI e baixar o OpenAPI JSON.
- Invocar cada endpoint (`GET /health`, `POST /api/v1/appointments`,
  `GET /api/v1/appointments/{id}`, `GET /api/v1/appointments`) com `curl`.
- Passar e verificar o header `X-Correlation-Id` nos logs JSON.
- Interpretar o envelope canônico de erro (`E_API_*`) para depuração.

---

## 2. Pré-requisitos

**Serviço necessário**: apenas `scheduling-api` publica porta no host (`8000:8000`). Os
demais serviços (`ocr-mcp`, `rag-mcp`, `generated-agent`) são internos ao Docker e não
precisam estar rodando para os exemplos abaixo.

```bash
# Subir somente a scheduling-api
docker compose up -d scheduling-api

# Aguardar healthcheck ficar healthy (até ~30 s)
docker compose ps scheduling-api
# scheduling-api   Up (healthy)   0.0.0.0:8000->8000/tcp
```

Verifique que o serviço está respondendo antes de continuar:

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

---

## 3. Como invocar

### Swagger UI e OpenAPI JSON

Abra `http://localhost:8000/docs` no navegador. O "Try it out" executa chamadas reais contra o
serviço em execução. O spec de máquina está disponível em:

```bash
curl -s http://localhost:8000/openapi.json | python -m json.tool | head -40
```

O JSON retornado é OpenAPI 3.1 válido. O `generated-agent` consome esta URL via
`SCHEDULING_OPENAPI_URL`.

### Tabela de endpoints

| Método | Caminho                          | Modelo de request      | Modelo de response  | Status 2xx |
|--------|----------------------------------|------------------------|---------------------|------------|
| GET    | `/health`                        | —                      | `HealthResponse`    | 200        |
| POST   | `/api/v1/appointments`           | `AppointmentCreate`    | `Appointment`       | 201        |
| GET    | `/api/v1/appointments/{id}`      | —                      | `Appointment`       | 200        |
| GET    | `/api/v1/appointments`           | query: `limit`/`offset`| `AppointmentList`   | 200        |

---

## 4. Contratos resumidos

Os schemas Pydantic completos estão em:

- `scheduling_api/scheduling_api/models.py` — `AppointmentCreate`, `Appointment`,
  `AppointmentList`, `HealthResponse`, `ExamRef`.
- `docs/specs/0004-scheduling-api/spec.md` — critérios de aceitação (AC1–AC17).
- `docs/ARCHITECTURE.md` § "Contratos — Scheduling API" — contrato normativo entre o agente
  ADK e a API.

Resumo dos campos principais de `AppointmentCreate`:

| Campo           | Tipo                         | Restrição                                      |
|-----------------|------------------------------|------------------------------------------------|
| `patient_ref`   | `string`                     | padrão `^anon-[a-z0-9]+$`; max 64 chars       |
| `exams`         | `list[ExamRef]`              | 1–20 itens; cada item tem `name` e `code`      |
| `scheduled_for` | `datetime` (timezone-aware)  | deve ser data/hora futura                      |
| `notes`         | `string` (opcional)          | max 500 chars; sem CPF/e-mail/telefone (PII)   |

`Appointment` (response) acrescenta: `id`, `status` (sempre `"scheduled"`), `created_at`.

A envelope de erro segue o shape canônico de ADR-0008 — ver seção 6.

---

## 5. Exemplos completos

### 5.1 POST `/api/v1/appointments` — criar agendamento

```bash
curl -s -X POST http://localhost:8000/api/v1/appointments \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: meu-teste-123" \
  -d '{
    "patient_ref": "anon-a7f3c1b2",
    "exams": [
      {"name": "Hemograma completo", "code": "HEMO-001"},
      {"name": "Glicemia em jejum",  "code": "GLIC-002"}
    ],
    "scheduled_for": "2026-12-01T09:00:00+00:00",
    "notes": "Trazer requisição médica"
  }' | python -m json.tool
```

Resposta 201 esperada (`Location` header aponta para `/api/v1/appointments/{id}`):

```json
{
  "id": "appt-4e2a1f8b",
  "status": "scheduled",
  "created_at": "2026-04-19T17:20:28.800Z",
  "patient_ref": "anon-a7f3c1b2",
  "exams": [
    {"name": "Hemograma completo", "code": "HEMO-001"},
    {"name": "Glicemia em jejum",  "code": "GLIC-002"}
  ],
  "scheduled_for": "2026-12-01T09:00:00Z",
  "notes": "Trazer requisição médica"
}
```

### 5.2 GET `/api/v1/appointments/{id}` — buscar por ID

```bash
curl -s http://localhost:8000/api/v1/appointments/appt-4e2a1f8b \
  -H "X-Correlation-Id: meu-teste-123" | python -m json.tool
```

Resposta 200 — o mesmo objeto `Appointment` criado anteriormente.

### 5.3 GET `/api/v1/appointments` — listar com paginação

```bash
# Página 1: primeiros 5 agendamentos
curl -s "http://localhost:8000/api/v1/appointments?limit=5&offset=0" | python -m json.tool
```

Resposta 200:

```json
{
  "items": [ /* lista de Appointment */ ],
  "total": 1,
  "limit": 5,
  "offset": 0
}
```

### 5.4 Header `X-Correlation-Id` nos logs

O header é ecoado na resposta e registrado em cada linha de log. Para verificar:

```bash
docker compose logs scheduling-api --tail=10
```

Saída JSON (uma linha por request):

```json
{"ts": "2026-04-19T17:20:28.800Z", "level": "INFO", "service": "scheduling-api",
 "correlation_id": "meu-teste-123", "event": "http.request",
 "method": "POST", "path": "/api/v1/appointments", "status_code": 201, "duration_ms": 1.99}
```

Se o header não for enviado, a API gera um ID automático com formato `api-<8 hex chars>`.

### 5.5 Envelope canônico de erro

**422 — payload inválido (`E_API_VALIDATION`)**:

```bash
curl -s -X POST http://localhost:8000/api/v1/appointments \
  -H "Content-Type: application/json" \
  -d '{"patient_ref": "joao silva", "exams": [], "scheduled_for": "2020-01-01T00:00:00Z"}' \
  | python -m json.tool
```

Resposta 422:

```json
{
  "error": {
    "code": "E_API_VALIDATION",
    "message": "String should match pattern '^anon-[a-z0-9]+$'",
    "hint": "Consulte /docs para o contrato da API",
    "path": "body.patient_ref",
    "context": {
      "errors": [
        {"loc": ["body", "patient_ref"], "msg": "String should match pattern '^anon-[a-z0-9]+$'"}
      ]
    }
  },
  "correlation_id": "api-3c7d9a1e"
}
```

**404 — ID inexistente (`E_API_NOT_FOUND`)**:

```bash
curl -s http://localhost:8000/api/v1/appointments/appt-inexistente | python -m json.tool
```

Resposta 404:

```json
{
  "error": {
    "code": "E_API_NOT_FOUND",
    "message": "Agendamento 'appt-inexistente' não encontrado",
    "hint": "Confirme o ID do agendamento",
    "path": "path.id",
    "context": null
  },
  "correlation_id": "api-5f2b8c0d"
}
```

---

## 6. Troubleshooting

| Sintoma | Código canônico | Causa provável | Ação |
|---------|----------------|----------------|------|
| 422 com `"code": "E_API_VALIDATION"` | `E_API_VALIDATION` | Campo faltando, tipo errado ou `patient_ref` sem padrão `anon-*`; `scheduled_for` no passado; `exams` vazio ou com mais de 20 itens; `notes` com CPF/e-mail/telefone | Leia `hint` e `path` na resposta; consulte `/docs` |
| 413 com `"code": "E_API_PAYLOAD_TOO_LARGE"` | `E_API_PAYLOAD_TOO_LARGE` | Body da requisição excede 256 KB | Reduza o payload; verifique `notes` ou lista de exames excessivamente grande |
| 404 com `"code": "E_API_NOT_FOUND"` | `E_API_NOT_FOUND` | ID do agendamento não existe no store (memória reiniciada ao restartar o serviço) | Verifique o `id` retornado no POST; o store é in-memory — reiniciar o container limpa os dados |
| 500 com `"code": "E_API_INTERNAL"` | `E_API_INTERNAL` | Erro interno não classificado; detalhes nunca expostos ao cliente | Consulte `docker compose logs scheduling-api`; abra issue com o `correlation_id` da resposta |
| 504 com `"code": "E_API_TIMEOUT"` | `E_API_TIMEOUT` | O handler não respondeu em 10 s | Verifique `docker compose ps`; reinicie o serviço se necessário |
| Swagger UI não carrega (`ERR_CONNECTION_REFUSED`) | — | Container ainda não está `healthy` ou porta 8000 não mapeada | Execute `docker compose ps scheduling-api`; aguarde status `(healthy)` |

---

## 7. Onde estender
- **Novo campo no contrato**: edite `scheduling_api/scheduling_api/models.py` e atualize
  `docs/ARCHITECTURE.md` § "Contratos — Scheduling API". Coordene com
  `docs/specs/0004-scheduling-api/plan.md` (seção DbC) — mudanças ecoam no agente ADK.

- **Novo endpoint**: adicione rota em `scheduling_api/scheduling_api/routes/` seguindo o
  padrão `response_model` + `summary` + `tags` dos arquivos existentes.

- **Troca do storage in-memory**: o repositório está em
  `scheduling_api/scheduling_api/repository.py` atrás da interface `AppointmentRepository`.
  Implemente uma nova classe e registre via `dependency_overrides` sem tocar nas rotas.

- **Referência normativa**: `docs/specs/0004-scheduling-api/plan.md` — Design by Contract de
  cada rota e invariantes do repositório.
