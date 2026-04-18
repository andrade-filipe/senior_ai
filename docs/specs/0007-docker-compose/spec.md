---
id: 0007-docker-compose
title: Dockerfiles e docker-compose.yml com healthchecks para o stack completo
status: approved
linked_requirements: [R07]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O desafio exige conteinerização completa com `docker-compose up` subindo **todos** os serviços (MCPs + API + agente) em um único comando. Sem este bloco, o avaliador precisaria configurar cinco ambientes Python manualmente — risco de avaliação.

- O que falta hoje? Um Dockerfile por serviço (`ocr_mcp`, `rag_mcp`, `scheduling_api`, `generated_agent`), o `docker-compose.yml` orquestrador, `.dockerignore` em cada serviço, `.env.example` consolidado na raiz.
- Quem é afetado? Avaliador (roda `docker compose up`), Bloco 8 (E2E depende do compose subindo limpo), CI (job `docker build`).
- Por que importa agora? Porta de entrada do avaliador — UX ruim aqui compromete a percepção de "engenharia e infraestrutura" ([`docs/REQUIREMENTS.md`](../../REQUIREMENTS.md) § "Critérios de avaliação").

## User stories

- Como **avaliador**, quero rodar `docker compose up` e ver os quatro serviços subirem (MCPs + API + agente pronto para rodar via `docker compose run agent`).
- Como **devops-engineer**, quero imagens enxutas construídas com `uv pip install --system` (ADR-0005) para tempo de build aceitável.
- Como **qa-engineer**, quero healthchecks determinísticos para que o E2E (Bloco 8) saiba quando a API está pronta para receber requisições.
- Como **developer**, quero que nenhum container exponha portas ao host que não sejam estritamente necessárias (GUIDELINES § 7).

## Critérios de aceitação

### Imagens

- [AC1] Cada Dockerfile declara base `python:3.12-slim` (GUIDELINES § 1).
- [AC2] Cada Dockerfile instala deps via `uv pip install --system -r requirements.txt` (ou equivalente `uv sync --frozen`) conforme ADR-0005.
- [AC3] Cada `CMD` usa formato exec (lista) — `CMD ["python", "-m", "scheduling_api"]` etc. (GUIDELINES § 7).
- [AC4] Cada serviço possui `.dockerignore` que exclui `.venv`, `__pycache__`, `tests/`, `.git`, `docs/`.
- [AC5] Dado qualquer Dockerfile, quando `docker build` roda, então completa sem erros — verificado no job `docker` do CI (ADR-0005).

### Compose

- [AC6] O arquivo `docker-compose.yml` na raiz declara quatro serviços: `ocr-mcp`, `rag-mcp`, `scheduling-api`, `generated-agent`.
- [AC7] `scheduling-api` expõe `8000:8000` ao host; MCPs **não** publicam portas (rede interna apenas); `generated-agent` roda como comando one-shot (sem portas expostas).
- [AC8] `scheduling-api` declara `healthcheck` HTTP em `/health` com `interval`, `timeout`, `retries` configurados.
- [AC9] `generated-agent` declara `depends_on` com `condition: service_healthy` para `scheduling-api` e `condition: service_started` para `ocr-mcp` e `rag-mcp` (ADR-0001 deixa explícito: MCPs usam `service_started`).
- [AC10] Variáveis de ambiente do `generated-agent` são lidas de `.env` conforme [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Variáveis de ambiente consolidadas" — `OCR_MCP_URL=http://ocr-mcp:8001/sse`, etc.

### Quickstart

- [AC11] Dado um clone limpo do repo + `.env` preenchido a partir de `.env.example`, quando executado `docker compose up -d ocr-mcp rag-mcp scheduling-api`, então os três serviços ficam `healthy`/`started` dentro de 60 s (inspeção manual; fixado por AC no Bloco 8).
- [AC12] Dado os serviços up, quando executado `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`, então o agente roda o fluxo end-to-end e sai com código 0.

### Segurança e observabilidade

- [AC13] Nenhuma imagem final contém `.env` (`.dockerignore` exclui) — verificado via `docker image inspect` / lista de layers.
- [AC14] Cada serviço emite logs JSON para stdout ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Formato de log") e o compose captura via driver default.
- [AC15] Dado qualquer `HEALTHCHECK` em Dockerfile ou `healthcheck:` em `docker-compose.yml`, quando inspecionado, então declara explicitamente `interval`, `timeout`, `retries` e `start_period` — nenhum campo usa defaults implícitos (reforço da disciplina de timeouts de [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md)).
- [AC16] Dado o `docker-compose.yml`, quando inspecionado, então **nenhum serviço** monta o socket Docker (`/var/run/docker.sock`), roda em `privileged: true`, ou declara `network_mode: host` — hardening de superfície de ataque.

## Robustez e guardrails

### Happy Path

Avaliador executa `docker compose up -d ocr-mcp rag-mcp scheduling-api` → três serviços sobem; `scheduling-api` reporta `healthy` em < 30 s; `generated-agent` é executado via `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` e sai com exit 0.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| `HEALTHCHECK` sem `interval`/`timeout`/`retries`/`start_period` explícitos | rejeitar no review | — | AC15 |
| Serviço monta `/var/run/docker.sock` | rejeitar no review | — | AC16 |
| Serviço roda `privileged: true` | rejeitar no review | — | AC16 |
| `.env` embarcado em imagem | `.dockerignore` exclui | — | AC13 |
| MCP expõe porta ao host | rejeitar no review | — | AC7 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| `healthcheck` em `scheduling-api` | `interval ≤ 10s`, `timeout ≤ 5s`, `retries ≤ 10`, `start_period ≤ 60s` | review block | AC15 |
| Portas expostas ao host | apenas `scheduling-api:8000` | review block | AC7 |
| `privileged`, socket Docker, `network_mode: host` | proibidos | review block | AC16 |

### Security & threats

- **Ameaça**: healthcheck sem timeout explícito pode travar o compose indefinidamente quando um serviço fica lento, fazendo o E2E do Bloco 8 flakar.
  **Mitigação**: AC15 obriga valores explícitos para `interval`, `timeout`, `retries`, `start_period` — alinhado a ADR-0008 § Timeouts (todo limite é explícito).
- **Ameaça**: serviço malicioso ou bug escalona privilégio montando socket Docker e cria outros containers.
  **Mitigação**: AC16 proíbe docker socket, `privileged`, `network_mode: host`. Code-reviewer rejeita PR que viole.
- **Ameaça**: MCP exposto ao host convida tráfego externo não auditado.
  **Mitigação**: AC7 já mantém MCPs em rede interna; AC16 reforça via proibição de `network_mode: host`.

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC8 | `/health` do `scheduling-api` (healthcheck) | Post |
| AC15 | `docker-compose.yml healthcheck:` | Invariant (timeouts explícitos ADR-0008) |
| AC16 | `docker-compose.yml service` | Invariant (hardening de privilégios) |

## Requisitos não-funcionais

- **Tamanho de imagem**: inspeção manual — nenhuma imagem final > 500 MB no MVP (sem hard gate).
- **Tempo de build**: build cache deve permitir rebuild parcial em < 30 s após primeiro build completo.
- **Rede**: uma única network `default` do compose; serviços se resolvem por nome (`ocr-mcp`, `rag-mcp`, etc.).
- **Reprodutibilidade**: `uv.lock` commitado por serviço (ADR-0005); build determinístico para versões pinadas.

## Clarifications

*(nenhuma — imagem base fixada como `python:3.12-slim` para todos os serviços, inclusive `generated_agent`. Google não publica imagem oficial ADK; a base única compartilha layers e reduz tempo de build. AC1 reforça.)*

## Fora de escopo

- Kubernetes manifests.
- CI/CD para publicar imagens em registry.
- TLS / certificados (rede interna).
- Volumes persistentes (API é in-memory).
- Multi-arch build (apenas `linux/amd64` no MVP).
