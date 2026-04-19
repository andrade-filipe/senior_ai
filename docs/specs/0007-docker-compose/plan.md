---
id: 0007-docker-compose
status: proposed
---

## Abordagem técnica

Um `Dockerfile` por serviço, `docker-compose.yml` na raiz, `.dockerignore` por serviço, `.env.example` consolidado (lista em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Variáveis de ambiente"). **Todos os Dockerfiles (inclusive `generated_agent/`) usam `python:3.12-slim` como imagem base** — Google não publica imagem oficial para ADK (ADK é distribuído como pacote pip), então reaproveitar a mesma base em todos os serviços compartilha layers entre builds e reduz tempo total. Consistente com [ADR-0005](../../adr/0005-dev-stack.md): base `python:3.12-slim`, `uv pip install --system`, `CMD` em formato exec. Guardrails de healthchecks explícitos e hardening de privilégios conforme [ADR-0008](../../adr/0008-robust-validation-policy.md).

Estrutura esperada ao fim do bloco:

```
Dockerfile.ocr_mcp            # (pode viver em ocr_mcp/Dockerfile)
Dockerfile.rag_mcp
Dockerfile.scheduling_api
Dockerfile.generated_agent
docker-compose.yml
.env.example                  # raiz
.dockerignore                 # raiz (compartilhado) + por serviço se necessário
```

Decisão pragmática: cada serviço recebe **seu próprio** Dockerfile em seu diretório (`ocr_mcp/Dockerfile`, etc.) para facilitar build context mínimo. Exceção: `generated_agent/Dockerfile` é **emitido pelo transpilador** (Bloco 2) — este bloco apenas consome e referencia.

### Dockerfile canônico (template)

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache .
COPY . .
CMD ["python", "-m", "<service_module>"]
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:<port>/health')" || exit 1
```

Para `ocr-mcp` e `rag-mcp`, healthcheck é `HEAD http://localhost:<port>/sse` retornando 200/405 (ADR-0001 — não temos `/health` HTTP nativo MCP).

### docker-compose.yml (esqueleto)

```yaml
services:
  ocr-mcp:
    build: ./ocr_mcp
    environment:
      - LOG_LEVEL=INFO
      - PII_DEFAULT_LANGUAGE=pt

  rag-mcp:
    build: ./rag_mcp
    environment:
      - LOG_LEVEL=INFO

  scheduling-api:
    build: ./scheduling_api
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 5s
      timeout: 3s
      retries: 10

  generated-agent:
    build: ./generated_agent
    env_file:
      - .env
    depends_on:
      scheduling-api:
        condition: service_healthy
      ocr-mcp:
        condition: service_started
      rag-mcp:
        condition: service_started
    volumes:
      - ./docs/fixtures:/fixtures:ro
    # Sem ports; roda sob demanda via `docker compose run`
```

### .env.example

Cópia das variáveis listadas em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Variáveis de ambiente", com placeholders explícitos (`GOOGLE_API_KEY=<your-key>`) e `GOOGLE_GENAI_USE_VERTEXAI=FALSE`. Arquivo **não** commita credenciais; `.gitignore` bloqueia `.env` real (GUIDELINES § 3).

## Data models

Nenhum modelo de dado introduzido. Apenas infraestrutura.

## Contratos

Contratos **consumidos** (forma fixa em outros blocos):
- Portas: `ocr-mcp:8001`, `rag-mcp:8002`, `scheduling-api:8000`.
- Healthcheck HTTP do `/health` na API (Bloco 4 AC1).
- Variáveis de ambiente consolidadas em ARCHITECTURE (Blocos 3, 4, 6).

Contrato **emitido**:
- Comando canônico: `docker compose up -d` sobe serviços; `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` dispara o fluxo.

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `/health` do `scheduling-api` (healthcheck) | serviço iniciado | responde `200 {"status":"ok"}` se dependências internas saudáveis | healthcheck nunca retorna 5xx com serviço declarado `healthy` pelo compose | AC8 | T013 `[DbC]` |
| `docker-compose.yml healthcheck:` | healthcheck declarado | todos os campos `interval`/`timeout`/`retries`/`start_period` explícitos (ADR-0008) | nenhum default implícito | AC15 | T032 `[DbC]` |
| `docker-compose.yml service` | serviço declarado | nenhum serviço monta socket Docker, `privileged`, ou `network_mode: host` | hardening de privilégios ADR-0008 | AC16 | T033 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo |
|---|---|---|
| `docker` engine | `^24` | Runtime |
| `docker compose` | `^v2.20` | Plugin (não legacy `docker-compose`) |
| `uv` no container | `^0.5` | Instalação rápida (ADR-0005) |
| `python:3.12-slim` | tag específica | Base imutável (GUIDELINES § 1) |

## Riscos

| Risco | Mitigação |
|---|---|
| Healthcheck MCP (SSE) via HEAD pode retornar 405/404 dependendo da lib. | ADR-0001 já prevê: usamos `service_started` para MCPs; healthcheck serve só para logs. |
| Imagem do `ocr-mcp` fica grande devido ao `pt_core_news_lg` (~500 MB). | Aceitável no MVP; inspecionar tamanho e registrar em evidência. Se virar dor, multi-stage ou `md` via ADR. |
| `generated_agent/Dockerfile` é emitido pelo transpilador mas precisa ser compatível com compose. | Template do Bloco 2 testado contra este compose em AC12 (smoke). |
| `.env` acidentalmente entra na imagem. | `.dockerignore` exclui (AC13); teste manual com `docker image inspect` na evidência. |
| `depends_on` com `service_healthy` trava se API nunca ficar healthy. | `retries=10`, timeout curto, logs em caso de falha. Bloco 8 adiciona wait-and-fail explícito no E2E. |
| Ordem de `build` em `docker compose up` pode mudar em versões futuras. | Documentar versão mínima do Compose em README; CI roda a mesma versão. |

## Estratégia de validação

- **Build test** (AC5): job `docker` do CI (ADR-0005) roda `docker build` em cada Dockerfile.
- **Compose up smoke** (AC11): teste manual scriptado no Bloco 8 — `docker compose up -d ocr-mcp rag-mcp scheduling-api` + `docker compose ps` assertando `healthy`/`running`.
- **Dockerfile lint** (opcional stretch): `hadolint` em CI.
- **PII em imagem** (AC13): inspeção `docker image inspect <image> | grep -i env` na evidência.
- **Cobertura**: não aplicável (infra não testável por unit); coverage field do relatório fica vazio.

**Estratégia de validação atualizada (ADR-0008)**:
- **Healthcheck explícito (AC15)**: teste `yaml.safe_load` sobre `docker-compose.yml` valida que todo `healthcheck:` contém as chaves `interval`, `timeout`, `retries`, `start_period` como strings não-vazias; análogo para `HEALTHCHECK` em Dockerfiles via regex.
- **Hardening de privilégios (AC16)**: teste `yaml.safe_load` valida que nenhum serviço tem `privileged: true`, `network_mode: host`, nem volume mapeando `/var/run/docker.sock`.

## Notas operacionais

- **Onde correm os testes de infra**: `tests/infra/` mora na raiz, mas o arnês é o venv do `scheduling_api` — `pyyaml>=6` foi adicionado ao seu `[dependency-groups].dev` (não à imagem de produção; apenas harness de teste). Racional: evita criar um pyproject raiz só para isto e mantém a política ADR-0005 "pyproject.toml por serviço". Se o CI futuramente separar jobs por serviço e estes testes precisarem correr fora do job de `scheduling_api`, mover o `pyyaml` para um `[dependency-groups].infra` em qualquer pyproject de serviço (ou criar um grupo compartilhado) fecha a dívida. Registrado como MINOR no review do 0007.

## Dependências entre blocos

- **Depende, em código/artefatos** — precisa que Blocos 3, 4, 5, 6 tenham Dockerfiles próprios (cada engenheiro entrega o `Dockerfile` do seu serviço junto com o código; devops-engineer **consolida** e escreve o compose).
- Em termos de **spec/contrato**: **independente** — formas, portas, env vars, healthchecks estão em ARCHITECTURE. Compose pode ser escrito em paralelo com os outros blocos **desde que os contratos sejam respeitados**.
- **Bloqueia** o Bloco 8 (E2E depende de `docker compose up` funcionar).
