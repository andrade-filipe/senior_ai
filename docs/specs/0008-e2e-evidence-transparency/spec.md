---
id: 0008-e2e-evidence-transparency
title: E2E + evidências consolidadas + README final com seção Transparência
status: approved
linked_requirements: [R08, R09, R10, R12]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

Mesmo com todos os blocos anteriores verdes individualmente, o desafio não está entregue até que: (a) exista um teste E2E automatizado que prove o fluxo completo funcionando com `docker compose`; (b) existam **evidências** reprodutíveis (logs, prints CLI, captura do Swagger) em `docs/EVIDENCE/`; (c) o `README.md` da raiz esteja em português, explique arquitetura, stack, quickstart e inclua a seção **Transparência e Uso de IA** (R12); (d) `sample_medical_order.png` e `spec.example.json` estejam commitados (R10).

- Quem é afetado? Avaliador (é o que ele vê primeiro) + mantenedor futuro.
- Por que importa agora? Fecha o desafio. Nenhum bloco anterior ganha a marcação `done` final sem cobertura por este.

## User stories

- Como **avaliador**, quero abrir `README.md` e em < 5 minutos rodar o quickstart e ver o agente processar a imagem de exemplo.
- Como **avaliador**, quero ler a seção "Transparência e Uso de IA" e entender exatamente quais partes foram escritas com IA, quais referências foram usadas e como o fluxo SDD+TDD foi aplicado.
- Como **mantenedor futuro**, quero abrir `docs/EVIDENCE/` e encontrar logs + screenshots + relatório de cobertura por marco.
- Como **avaliador**, quero que `pytest -m e2e` execute um cenário real com `docker compose` subindo e derrubando os serviços.

## Critérios de aceitação

### Teste E2E (R08) — política dupla (CI leve + manual completo)

- [AC1a] **E2E CI (automatizado, sem Gemini real)**: dado o repo em estado limpo, quando o GitHub Actions executa o job `e2e_ci` com `docker compose up -d` + aguarda healthchecks + roda `pytest -m e2e_ci`, então todas as suítes unit + integration dos serviços (`ocr-mcp`, `rag-mcp`, `scheduling-api`) passam **sem chamar Gemini real** — evita custo/rate limit/leak de segredo. Ao fim, o teardown `docker compose down -v` roda limpo.
- [AC1b] **E2E completo (manual, com Gemini real)**: dado o avaliador seguir o passo-a-passo do README ("Executar E2E completo"), quando executa `cp .env.example .env` (preenchendo `GOOGLE_API_KEY`) + `docker compose up -d` + `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`, então o agente roda o fluxo completo com Gemini, cria ao menos um `Appointment` na API, e imprime a tabela ASCII final no terminal. Evidência (logs + print da tabela) fica em `docs/EVIDENCE/0008-e2e-evidence-transparency.md`.
- [AC2] Dado o E2E (CI ou manual) rodando, quando os logs do `scheduling-api` são inspecionados, então contém um `event=http.request` com `method="POST"` e `path="/api/v1/appointments"` com `correlation_id` igual ao da CLI.
- [AC3] Dado o E2E rodando, quando o body do POST capturado é inspecionado, então o campo `patient_ref` casa `^anon-[a-z0-9]+$` (sem PII crua — reforça AC5 do Bloco 6).

### Evidências (R08)

- [AC4] `docs/EVIDENCE/` contém **um arquivo Markdown por bloco** (`0001-agentspec-schema.md`, ..., `0008-e2e-evidence-transparency.md`) — **sem agregador único**. Cada arquivo é produzido no passo 7 (evidence) do próprio bloco e contém: comandos reproduzíveis, trechos de log, screenshots CLI/Swagger, relatório de cobertura. O `README.md` final lista todos por link.
- [AC5] O arquivo de evidência do Bloco 4 inclui screenshot (PNG ou Markdown-embed) da Swagger UI em `/docs`.
- [AC6] O arquivo de evidência do Bloco 8 inclui o log completo de uma execução E2E bem-sucedida (trimado em linhas relevantes, com `correlation_id` destacado).

### Fixtures (R10)

- [AC7] O repo contém `docs/fixtures/sample_medical_order.png` (imagem de teste) e `docs/fixtures/spec.example.json` (JSON de exemplo correspondente ao schema do Bloco 1).
- [AC8] Dado `spec.example.json`, quando validado pelo schema do Bloco 1 e passado à CLI do transpilador (Bloco 2), então gera um `generated_agent/` sem erros.

### README principal (R09)

- [AC9] `README.md` na raiz está em **português** e contém: badge de CI (ADR-0005), diagrama de arquitetura (referência ao mermaid de `docs/ARCHITECTURE.md` ou inline), stack consolidada (`uv`, Gemini, ADK, MCP-SSE, FastAPI, Presidio), quickstart em três comandos ou menos, link para `docs/EVIDENCE/` e link para a seção Transparência.
- [AC10] `README.md` contém a seção **"Transparência e Uso de IA"** (R12) cobrindo: quais partes foram desenvolvidas com assistência de IA (Claude Code + subagentes), abordagem SDD+TDD adotada, principais referências consultadas (link explícito para `ai-context/LINKS.md`), e estratégia de orquestração (diagrama mental dos 8 subagentes).
- [AC11] `README.md` documenta a estrutura de diretórios (`docs/`, `ai-context/`, `transpiler/`, `security/`, etc.) em nível de 1 linha cada.

### Coerência final

- [AC12] `ai-context/STATUS.md` está atualizado com todos os 8 blocos em `done` e o histórico de checkpoints preenchido.
- [AC13] Todos os `spec.md` dos Blocos 1–7 estão em `status: implemented` com `docs/ARCHITECTURE.md` consistente com a implementação.

### Robustez end-to-end (ADR-0008)

- [AC14] Dado o E2E CI (AC1a) rodando, quando os logs de **todos** os serviços (`ocr-mcp`, `rag-mcp`, `scheduling-api`, `generated-agent`) são coletados, então **nenhum campo** em **nenhuma linha** casa os padrões de PII definidos em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII" — reforço da regra "no-PII-in-logs" de [ADR-0008 § No-PII-in-logs](../../adr/0008-robust-validation-policy.md). Script de auditoria (`scripts/audit_logs_pii.py`) roda após o teardown e aborta o job se encontrar padrão PII.
- [AC15] Dado um cenário de erro deliberadamente induzido (ex.: spec inválido na CLI do transpilador, imagem corrompida no agente, 422 na API), quando o erro é emitido em stderr ou body HTTP, então serializa exatamente no shape canônico ADR-0008 (`code`, `message`, `hint`, `path`, `context`) — validado em `tests/e2e/test_error_shape.py`.

### Rastreabilidade DbC

Não aplicável — este bloco herda invariantes dos blocos 1–7. Bloco de orquestração/fechamento que valida contratos externamente (E2E, evidências, README) sem introduzir pré/pós/invariantes próprios de função/classe. As tabelas DbC dos plans dos blocos 1–7 (com seus `AC ref` / `Task ref`) são o contrato semântico que o E2E aqui exercita ponta-a-ponta.

## Robustez e guardrails

### Happy Path

CI roda `e2e_ci` marker → compose sobe → healthchecks verdes → unit + integration suítes passam; `scripts/audit_logs_pii.py` varre logs coletados e não encontra PII; teardown limpo; job pinta verde.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| Log coletado contém padrão PII | audit script aborta CI | — | AC14 |
| Erro não-serializado no shape canônico | E2E teste falha | — | AC15 |
| `docker compose down -v` falha | `finally` captura e reporta | — | AC1a |
| Gemini rate-limit no E2E manual | documentado no README | — | AC1b |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| Logs coletados no E2E | zero matches de padrões PII (ARCHITECTURE) | CI red + `audit_logs_pii.py` exit ≠ 0 | AC14 |
| Forma de erro emitido | shape canônico `{code, message, hint, path, context}` | CI red | AC15 |

### Security & threats

- **Ameaça**: um bug em qualquer bloco leva à emissão de log com valor cru de CPF/nome em runtime — só detectável via auditoria E2E agregada.
  **Mitigação**: script de auditoria roda após cada execução E2E do CI (AC14); evidência do job contém contagem de matches (esperado zero).
- **Ameaça**: algum componente escapa do formato de erro canônico (ex.: FastAPI retorna `{"detail": ...}` default, ou CLI imprime `Exception: ...`), quebrando rastreabilidade entre serviços.
  **Mitigação**: testes E2E induzem erros em cada componente e validam shape canônico ADR-0008 (AC15).

## Requisitos não-funcionais

- **README**: único arquivo na raiz; < 500 linhas; linkeia `docs/` e `ai-context/` em vez de duplicar conteúdo.
- **E2E**: marcado `@pytest.mark.e2e` (skip por default local; ligado no CI opcionalmente); usa `docker compose -f` explícito para evitar colisão.
- **Evidências**: cada arquivo < 200 linhas; logs trimados para o essencial.
- **Idioma**: README em PT-BR (GUIDELINES § 6); screenshots podem ter UI em EN.

## Clarifications

*(nenhuma — política de E2E fixada em AC1a (CI leve, sem Gemini) + AC1b (manual completo, com Gemini). Formato de evidências fixado em AC4: um `.md` por bloco, sem agregador.)*

## Fora de escopo

- Publicação do projeto em PyPI / Docker Hub.
- Testes de performance / carga.
- Documentação de API em formatos diferentes de Swagger (ex.: Redoc).
- Tradução do README para EN (explicitamente fora — GUIDELINES § 6).
