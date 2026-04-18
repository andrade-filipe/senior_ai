---
id: 0007-docker-compose
status: todo
---

## Setup

- [ ] T001 — Criar `.dockerignore` na raiz (exclui `.venv`, `__pycache__`, `tests/`, `.git`, `docs/`, `ai-context/`, `.env`).
- [ ] T002 — Criar `.env.example` na raiz com as variáveis listadas em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Variáveis de ambiente".
- [ ] T003 [P] — Consolidar `ocr_mcp/Dockerfile` produzido no Bloco 3 (pode já existir; este bloco padroniza o template).
- [ ] T004 [P] — Consolidar `rag_mcp/Dockerfile` produzido no Bloco 3.
- [ ] T005 [P] — Consolidar `scheduling_api/Dockerfile` produzido no Bloco 4.
- [ ] T006 [P] — Consolidar `generated_agent/Dockerfile` produzido pelo transpilador (Bloco 2).
- [ ] T007 — Criar `docker-compose.yml` na raiz com os quatro serviços (esqueleto no plan).

## Tests (same-commit — smoke; infra sem unit tests dedicados)

- [ ] T010 [P] — Adicionar a `tests/infra/test_dockerfiles.py::test_each_dockerfile_builds` marcado `@pytest.mark.infra` — `subprocess.run(["docker", "build", "-t", "<tag>", "."])` para cada serviço (AC5).
- [ ] T011 [P] — Teste [AC6] em `tests/infra/test_compose.py::test_compose_declares_four_services` usando `yaml.safe_load`.
- [ ] T012 [P] — Teste [AC7] em `tests/infra/test_compose.py::test_only_scheduling_api_publishes_port`.
- [ ] T013 [P] [DbC] — Teste [AC8] em `tests/infra/test_compose.py::test_scheduling_api_has_health_healthcheck` — DbC: `/health` healthcheck.Post (responde 200 ok se saudável).
- [ ] T014 [P] — Teste [AC9] em `tests/infra/test_compose.py::test_agent_depends_on_with_conditions`.
- [ ] T015 [P] — Teste [AC10] em `tests/infra/test_compose.py::test_agent_env_matches_architecture_list`.
- [ ] T016 [P] — Teste [AC13] em `tests/infra/test_dockerignore.py::test_dockerignore_excludes_env` (lê `.dockerignore` e valida entries).
- [ ] T032 [P] [DbC] — Teste [AC15] em `tests/infra/test_compose.py::test_healthcheck_fields_explicit` (para cada `healthcheck:` em `docker-compose.yml`, assert que `interval`, `timeout`, `retries`, `start_period` estão declarados e são strings não-vazias; análogo para `HEALTHCHECK` em Dockerfiles via regex `--interval=`, `--timeout=`, `--retries=`, `--start-period=`) — DbC: `docker-compose.yml healthcheck:.Invariant`.
- [ ] T033 [P] [DbC] — Teste [AC16] em `tests/infra/test_compose.py::test_no_privileged_or_docker_socket` (`yaml.safe_load` valida que nenhum serviço declara `privileged: true`, `network_mode: host`, nem monta `/var/run/docker.sock` em `volumes:`) — DbC: `docker-compose.yml service.Invariant`.

## Implementation (GREEN)

- [ ] T020 — Preencher `docker-compose.yml` seguindo esqueleto do plan (ADR-0001, AC6–AC10).
- [ ] T021 — Garantir que Dockerfiles consolidados têm `CMD` em formato lista (AC3), base `python:3.12-slim` (AC1), `uv pip install --system` (AC2).
- [ ] T022 — Adicionar `.dockerignore` específico em cada serviço se o contexto de build for local ao diretório (otimização — opcional).
- [ ] T023 — Adicionar `HEALTHCHECK` no `scheduling_api/Dockerfile` apontando para `/health` (AC8).
- [ ] T024 — Adicionar pasta `volumes: ./docs/fixtures:/fixtures:ro` no `generated-agent` para expor imagem de teste (AC12).
- [ ] T025 — Documentar em comentário no `docker-compose.yml` a versão mínima (`# requires docker compose v2.20+`).

## Refactor

- [ ] T030 — Verificar tamanho de cada imagem (`docker image ls`); se `ocr-mcp` >> 600 MB, abrir nota em evidência (sem ADR agora).
- [ ] T031 — Rodar `hadolint` em cada Dockerfile (opcional, stretch); fixar warnings fáceis.

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0007-docker-compose.md`: `docker compose config` (dump sanitizado), `docker compose up -d` + `docker compose ps` mostrando `healthy`/`running`, `docker image ls` com tamanhos (AC11, AC14).
- [ ] T091 — Anexar `docker image inspect <tag> | grep Env` mostrando que `.env` não está embarcado (AC13).

## Paralelismo

Setup `[P]` (T003–T006) em paralelo — cada Dockerfile em serviço distinto. Tests `[P]` (T010–T016) amplo. GREEN: T020 (compose) é sequencial; T021–T024 podem rodar em paralelo por serviço.

Dependência cross-bloco: T003–T006 precisam que Blocos 2, 3, 4 tenham entregue seus Dockerfiles base; pode começar assim que qualquer um deles termina GREEN.
