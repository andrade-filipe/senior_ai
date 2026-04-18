# FastAPI + Docker — Referência Consolidada

## 1. Stack alvo (2026)
- Python 3.12 ou 3.13.
- FastAPI com Pydantic v2.
- Uvicorn 0.42+ (não precisa de Gunicorn em dev; em prod pode usar `uvicorn --workers`).

## 2. Estrutura sugerida
```
scheduling_api/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI()
│   ├── routers/
│   │   └── appointments.py
│   ├── schemas/
│   │   └── appointment.py    # Pydantic v2 models
│   ├── services/
│   │   └── scheduler.py
│   ├── storage/
│   │   └── memory.py         # in-memory store mock
│   └── core/
│       ├── config.py         # Settings
│       └── logging.py
├── tests/
├── Dockerfile
└── requirements.txt
```

## 3. Esqueleto do `main.py`
```python
from fastapi import FastAPI
from .routers import appointments
from .schemas.health import HealthResponse

app = FastAPI(
    title="Lab Scheduling API",
    version="1.0.0",
    description="API fictícia de agendamentos de exames laboratoriais.",
)

app.include_router(appointments.router, prefix="/api/v1")

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=app.version)
```

## 4. Contrato mínimo (rascunho)
- `POST /api/v1/appointments` — cria agendamento. Body: `{patient_id, exams: [{name, code}], scheduled_for, notes}`.
- `GET /api/v1/appointments/{id}` — recupera agendamento.
- `GET /api/v1/exams` — lista catálogo (opcional, para inspeção).
- `GET /health` — liveness/readiness.

## 5. Pydantic v2 schemas
```python
from pydantic import BaseModel, Field
from datetime import datetime

class ExamItem(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., pattern=r"^[A-Z0-9-]{2,20}$")

class AppointmentCreate(BaseModel):
    patient_ref: str  # referência anonimizada, não PII
    exams: list[ExamItem]
    scheduled_for: datetime
    notes: str | None = None

class AppointmentRead(AppointmentCreate):
    id: str
    status: str
    created_at: datetime
```

## 6. Dockerfile (prod-oriented)
```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 7. docker-compose (esqueleto)
```yaml
services:
  scheduling-api:
    build: ./scheduling_api
    ports: ["8000:8000"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
  ocr-mcp:
    build: ./ocr_mcp
    ports: ["8001:8001"]
  rag-mcp:
    build: ./rag_mcp
    ports: ["8002:8002"]
  agent:
    build: ./generated_agent
    depends_on:
      scheduling-api: { condition: service_healthy }
      ocr-mcp: { condition: service_started }
      rag-mcp: { condition: service_started }
    env_file: .env
```

## 8. Boas práticas
- Use `response_model` em todas as rotas.
- `tags` e `summary` em cada endpoint — reflete no Swagger.
- `exec` form no `CMD` para lifespan correto.
- Separar camadas (router/service/storage) para testabilidade.
- Testes com `httpx.AsyncClient` + `pytest-asyncio`.

## 9. Fontes
- `https://fastapi.tiangolo.com/deployment/docker/`
- `https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/`
