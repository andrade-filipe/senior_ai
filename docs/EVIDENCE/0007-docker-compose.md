# Evidência — Bloco 0007 · Docker Compose e Containerização

- **Spec**: [`docs/specs/0007-docker-compose/spec.md`](../specs/0007-docker-compose/spec.md)
- **Status**: `done` — fechado em 2026-04-19.
- **Ambiente**: Windows 11, Docker Desktop 29.3.1, `docker compose v2`.
- **Arquivo**: `docker-compose.yml` na raiz do repo.

## Resumo

- 4 Dockerfiles criados: `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, `generated_agent/`.
- `docker-compose.yml` declara 4 serviços com healthchecks explícitos.
- Apenas `scheduling-api` expõe porta ao host (`8000:8000`).
- `generated-agent` usa `depends_on.service_healthy` para `scheduling-api` e `service_started` para MCPs.
- 31 testes de infra em `tests/infra/` verificam o compose sem Docker daemon.

## Comandos reproduzíveis

```bash
# Subir stack completa (exceto generated-agent que é one-shot):
docker compose up -d ocr-mcp rag-mcp scheduling-api

# Verificar saúde:
docker compose ps

# Derrubar:
docker compose down -v
```

## Testes de infra (sem daemon)

```bash
cd scheduling_api
uv run pytest ../tests/infra/ -v --no-cov
```

Resultado:
```
tests/infra/test_compose.py::TestAC6FourServices::test_compose_declares_four_services PASSED
tests/infra/test_compose.py::TestAC7PortExposure::test_only_scheduling_api_publishes_port PASSED
tests/infra/test_compose.py::TestAC8HealthcheckHttp::test_scheduling_api_has_health_healthcheck PASSED
tests/infra/test_compose.py::TestAC9DependsOn::test_agent_depends_on_with_conditions PASSED
tests/infra/test_compose.py::TestAC10AgentEnv::test_agent_env_matches_architecture_list PASSED
tests/infra/test_compose.py::TestAC15HealthcheckExplicit::test_healthcheck_fields_explicit PASSED
tests/infra/test_compose.py::TestAC16SecurityHardening::test_no_privileged_or_docker_socket PASSED
...
```

## Saída `docker compose up -d` (build + start)

```
[+] Building 9.1s (25/25) FINISHED
 Image senior_ia-ocr-mcp       Built (spaCy + Presidio + security)
 Image senior_ia-rag-mcp       Built (mcp + rapidfuzz)
 Image senior_ia-scheduling-api Built (fastapi + uvicorn)
 Network senior_ia_default     Created
 Container senior_ia-ocr-mcp-1       Started
 Container senior_ia-rag-mcp-1       Started
 Container senior_ia-scheduling-api-1 Started
```

## Saída `docker compose ps` (após healthchecks)

```
NAME                           SERVICE           STATUS    PORTS
senior_ia-ocr-mcp-1           ocr-mcp           running
senior_ia-rag-mcp-1           rag-mcp           running
senior_ia-scheduling-api-1    scheduling-api    running   0.0.0.0:8000->8000/tcp
```

## Healthchecks configurados

| Serviço | Teste | interval | timeout | retries | start_period |
|---|---|---|---|---|---|
| `ocr-mcp` | `urllib.request.urlopen http://localhost:8001/sse` | 10s | 5s | 3 | 15s |
| `rag-mcp` | `urllib.request.urlopen http://localhost:8002/sse` | 10s | 5s | 3 | 15s |
| `scheduling-api` | `urllib.request.urlopen http://localhost:8000/health` | 10s | 3s | 5 | 30s |

## Mapeamento AC → teste/evidência

| AC | Verificação | Local |
|---|---|---|
| AC6 — 4 serviços | `test_compose_declares_four_services` | `tests/infra/test_compose.py` |
| AC7 — só scheduling-api expõe porta | `test_only_scheduling_api_publishes_port` | `tests/infra/test_compose.py` |
| AC8 — healthcheck aponta `/health` | `test_scheduling_api_has_health_healthcheck` | `tests/infra/test_compose.py` |
| AC9 — depends_on correto | `test_agent_depends_on_with_conditions` | `tests/infra/test_compose.py` |
| AC10 — env usa DNS compose | `test_agent_env_matches_architecture_list` | `tests/infra/test_compose.py` |
| AC12 — fixtures montadas | volume `./docs/fixtures:/fixtures:ro` | `docker-compose.yml` |
| AC15 — healthcheck campos explícitos | `test_healthcheck_fields_explicit` | `tests/infra/test_compose.py` |
| AC16 — sem privileged/socket | `test_no_privileged_or_docker_socket` | `tests/infra/test_compose.py` |
