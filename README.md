# Desafio Técnico Sênior IA

Transpilador JSON → Agente Google ADK + dois servidores MCP (OCR e RAG) via SSE + API FastAPI de agendamento + camada PII em dupla barreira, tudo empacotado em Docker Compose. Recebe um `spec.json` descrevendo o agente, emite um pacote Python `generated_agent/` e executa um fluxo end-to-end que lê um pedido médico (imagem), busca códigos dos exames num catálogo e agenda a consulta via API — anonimizando PII antes de qualquer chamada a LLM ou persistência.

## Quickstart

Pré-requisitos:

- Docker Desktop v2.20+ (testado em 29.3.1 no Windows 11).
- Python 3.12 via [`uv`](https://docs.astral.sh/uv/) (gerenciado por `uv python install`).
- `GOOGLE_API_KEY` válida para rodar o passo E2E com Gemini 2.5 Flash.

```bash
# 1. Clonar e configurar
git clone <repo-url>
cd Senior_IA
cp .env.example .env
# Editar .env: preencher GOOGLE_API_KEY=AIza...

# 2. Subir stack (3 serviços de infraestrutura)
docker compose up -d ocr-mcp rag-mcp scheduling-api

# 3. Aguardar healthchecks (até 60s)
docker compose ps

# 4. Executar agente com imagem de exemplo
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png

# 5. Teardown
docker compose down -v
```

Os comandos acima estão em `docs/EVIDENCE/0008-e2e-evidence-transparency.md` (AC1b) e são idênticos aos usados na suíte E2E para evitar divergência entre runbook e teste.

Após o passo 4 o agente imprime no terminal uma tabela ASCII com os exames identificados, seus códigos do catálogo RAG e a confirmação do agendamento criado na `scheduling-api`. O corpo do `POST /api/v1/appointments` enviado pelo agente carrega `patient_ref=anon-<hash>` — nenhum nome, CPF, telefone ou e-mail trafega.

Swagger público da API: [http://localhost:8000/docs](http://localhost:8000/docs).

## Stack

Decisões fechadas em [ADR-0005](docs/adr/0005-dev-stack.md):

- **Python 3.12** + [`uv`](https://docs.astral.sh/uv/) 0.11+ como gerenciador de dependências e runner de comandos (`uv sync`, `uv run`).
- **Pydantic v2** para o schema `AgentSpec` e para todos os modelos HTTP da `scheduling-api`.
- **FastAPI** + **Uvicorn** na API; **FastMCP** (SDK oficial `mcp[cli]`) nos dois servidores MCP, transporte **SSE** ([ADR-0001](docs/adr/0001-mcp-transport-sse.md)).
- **Google ADK** (`google-adk >= 1.0`) no agente gerado, modelo **Gemini 2.5 Flash** via API direta.
- **Microsoft Presidio** + 4 custom recognizers brasileiros (CPF/CNPJ/RG/Phone) com validação de dígito verificador ([ADR-0003](docs/adr/0003-pii-double-layer.md)).
- **Jinja2** + gate `ast.parse` no transpilador ([ADR-0002](docs/adr/0002-transpiler-jinja-ast.md)).
- **rapidfuzz** + catálogo CSV de 115 exames SIGTAP no RAG MCP ([ADR-0007](docs/adr/0007-rag-fuzzy-and-catalog.md)).
- Imagens Docker em `python:3.12-slim`; healthchecks com `urlopen(..., timeout=2)`.
- **GitHub Actions** mínimo para smoke de CI.

## Arquitetura

Cinco serviços na rede do Compose, mais o transpilador que roda em build-time:

```
                         ┌─────────────────────┐
                         │      Host / Dev     │
                         └──────────┬──────────┘
                                    │ CLI
              ┌─────────────────────┴───────────────────────┐
              │                Docker Compose               │
              │                                             │
              │   ┌──────────────┐                          │
              │   │ generated-   │  HTTP POST /appointments │
              │   │   agent      │─────────────────────────▶│
              │   │ (ADK + CLI)  │                          │
              │   └───┬─────┬────┘                          │
              │       │     │                               │
              │   SSE │     │ SSE                           │
              │       ▼     ▼                               │
              │   ┌──────┐ ┌──────┐     ┌──────────────┐    │
              │   │ ocr- │ │ rag- │     │ scheduling-  │    │
              │   │ mcp  │ │ mcp  │     │    api       │    │
              │   │:8001 │ │:8002 │     │    :8000     │    │
              │   └──────┘ └──────┘     └──────────────┘    │
              │                                             │
              └─────────────────────────────────────────────┘

  transpiler (build-time)  —  spec.json ──▶ generated_agent/
```

Única porta publicada ao host é `scheduling-api:8000` (para expor Swagger). OCR e RAG só são acessíveis dentro da rede Compose, o que impede acesso direto bypassando o agente. Detalhes de contratos (schemas, taxonomia de erros, formato de log estruturado, guardrails) em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); narrativa ponta a ponta do fluxo em [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md).

## Onde encontrar o quê

| Quero… | Onde olhar |
|---|---|
| Rodar rapidamente | [Quickstart](#quickstart) acima. |
| Entender o que acontece passo a passo quando o agente roda | [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md). |
| Chamar uma funcionalidade isolada (transpilador, OCR, RAG, API, agente, PII) | [`docs/tutorials/`](docs/tutorials/README.md) — seis tutoriais focados. |
| Executar o E2E manual com Gemini real (T021) | [`docs/runbooks/e2e-manual-gemini.md`](docs/runbooks/e2e-manual-gemini.md). |
| Consultar decisões arquiteturais | [`docs/adr/`](docs/adr/). |
| Verificar evidências de funcionamento por bloco | [`docs/EVIDENCE/`](docs/EVIDENCE/). |
| Rastrear requisitos originais do desafio | [`docs/DESAFIO.md`](docs/DESAFIO.md) + [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md). |
| Ver as fontes externas que apoiaram as decisões | [`docs/REFERENCES.md`](docs/REFERENCES.md). |

## Estrutura do repositório

```
transpiler/          Gerador JSON→Python; schema Pydantic AgentSpec; CLI + templates Jinja2.
ocr_mcp/             Servidor MCP-SSE de OCR mock (hash→texto canned) com PII mask embutido.
rag_mcp/             Servidor MCP-SSE de RAG com catálogo CSV de 115 exames + rapidfuzz.
scheduling_api/      FastAPI com Swagger em /docs; CRUD in-memory; middlewares de correlation_id e timeout.
security/            Presidio + 4 recognizers BR + hard timeout; expõe pii_mask() e make_pii_callback() ADK.
generated_agent/     Saída do transpilador: agente ADK pronto para uv run python -m generated_agent.
docs/                Entrega humana — DESAFIO, REQUIREMENTS, ARCHITECTURE, ADRs, specs, evidências.
ai-context/          Contexto de trabalho da IA — GUIDELINES, WORKFLOW, STATUS, LINKS, references.
tests/               Testes infra e E2E multi-serviço (marcadores @infra e @e2e_ci).
scripts/             Utilitários operacionais (ex: audit_logs_pii.py).
```

## Testes

A suíte é dividida por serviço e por escopo. Cada pacote Python é um projeto `uv` independente com `pyproject.toml` próprio.

```bash
# Testes unitários (sem Docker) — rápido, ~30s por serviço
cd scheduling_api && uv run pytest -m "not infra and not e2e_ci"
cd transpiler     && uv run pytest
cd ocr_mcp        && uv run pytest
cd rag_mcp        && uv run pytest
cd security       && uv run pytest
cd generated_agent && uv run pytest -m "not integration"

# Testes infra + E2E (com compose de pé)
docker compose up -d ocr-mcp rag-mcp scheduling-api
cd scheduling_api && uv run pytest ../tests/e2e -m e2e_ci -v --no-cov
```

Cobertura atual nos módulos configurados:

| Módulo | Cobertura | Observação |
|---|---|---|
| `transpiler/` | 97.73% | `mypy --strict` limpo. |
| `scheduling_api/` | 95% | 36 testes unit + middlewares. |
| `ocr_mcp/` | alta | 25 testes. |
| `rag_mcp/` | alta | 34 testes. |
| `security/` | 76.62% | Caminhos de boot spaCy/multiprocessing não exercitados em unit; ADR-0004 admite floor inferior com justificativa documentada em `docs/EVIDENCE/0005-pii-guard.md`. |

Smoke de CI roda em GitHub Actions a cada push. Evidências por bloco ficam em `docs/EVIDENCE/0001..0008-*.md`, cada uma com comandos reproduzíveis, logs trimados e mapa `AC → teste`.

## Transparência e uso de IA

Este projeto foi co-construído com **Claude Code (Anthropic)** atuando como assistente de engenharia sob direção humana. A seção abaixo descreve com honestidade como a IA foi usada, quais barreiras de qualidade estão no lugar e onde o humano mantém a decisão final.

### Método: SDD + TDD pragmático

Todo bloco de trabalho segue o ciclo formalizado em [ADR-0004](docs/adr/0004-sdd-tdd-workflow.md), detalhado em [`ai-context/WORKFLOW.md`](ai-context/WORKFLOW.md):

```
1. Requisito → 2. Spec → 3. Plan → 4. Tasks → [checkpoint humano #1 — coletivo]
                                                    ↓
[checkpoint #2] ← 9. Docs ← 8. Evidence ← 7. Review ← 6. Tests → 5. Code
```

Nenhum teste ou linha de código é escrito antes do checkpoint #1. Specs são o artefato primário; código é a expressão delas num stack específico. Quando os dois divergem, o spec é atualizado primeiro. Test-first é obrigatório em `transpiler/` e `security/`; same-commit nos demais. A lista completa de specs vive em `docs/specs/NNNN-<slug>/` com tripla `spec.md` / `plan.md` / `tasks.md`.

### Oito subagentes especializados

Em `.claude/agents/` há oito agentes Claude com missões distintas e permissões de escrita restritas por pasta. O orquestrador delega para o agente de domínio em cada bloco.

| Agente | Papel | Quando foi invocado |
|---|---|---|
| `software-architect` | Decompõe trabalho, escreve ADRs, mantém contratos, abre/fecha specs. Opus. | Fases 0, 0.5 e checkpoints #1/#2 de todos os 8 blocos. |
| `transpiler-engineer` | Implementação do schema `AgentSpec` + templates Jinja2 + CLI do transpilador. | Blocos 0001 e 0002. |
| `adk-mcp-engineer` | Servidores MCP-SSE e agente ADK consumidor. | Blocos 0003 e 0006. |
| `fastapi-engineer` | API de agendamento, middlewares, taxonomia de erros canônica. | Bloco 0004. |
| `security-engineer` | Camada PII com Presidio + recognizers BR + hard timeout. | Bloco 0005. |
| `devops-engineer` | Dockerfiles, `docker-compose.yml`, healthchecks. | Bloco 0007. |
| `qa-engineer` | Testes, cobertura, fixtures, evidências por marco. | Todos os blocos + Bloco 0008. |
| `code-reviewer` | Revisão independente antes de cada marco; rejeita PRs sem rastreabilidade AC↔teste↔código. Opus. | Antes de cada commit narrativo de implementação. |

Toda delegação termina com handoff explícito e o `code-reviewer` (modelo Opus, independente) audita o resultado antes do merge. Três rodadas de review foram necessárias no Bloco 0006 e duas no Bloco 0007 — com blockers reais sendo capturados (por exemplo: `CorrelationIdMiddleware` resetava ContextVar antes do log; `root_agent` disparava `httpx.get` bloqueante no import).

### Contexto vivo em `ai-context/`

Paralelo a `docs/` (entrega humana), existe `ai-context/` como memória operacional da IA:

- [`ai-context/GUIDELINES.md`](ai-context/GUIDELINES.md) — padrões de código, testes, segurança e git aplicados pelos agentes.
- [`ai-context/WORKFLOW.md`](ai-context/WORKFLOW.md) — ciclo SDD + TDD de 9 passos com donos por etapa.
- [`ai-context/STATUS.md`](ai-context/STATUS.md) — quadro vivo de progresso por bloco; atualizado a cada checkpoint.
- [`ai-context/LINKS.md`](ai-context/LINKS.md) — log auditável de **toda fonte externa** consultada (ADK, MCP, Presidio, rapidfuzz, papers agentic). Cada decisão técnica tem a fonte primária rastreável.
- [`ai-context/references/DESIGN_AUDIT.md`](ai-context/references/DESIGN_AUDIT.md) — auditoria crítica do design pré-implementação. Capturou e corrigiu: Gemini `2.0-flash` deprecated → `2.5-flash`; Presidio BR recognizers documentados como custom. Uma afirmação da auditoria sobre `SseConnectionParams` foi corrigida em 2026-04-19 após inspeção do pacote ADK 1.31.0 instalado — a classe existe e é a única compatível com FastMCP `transport="sse"` (ver nota de correção no § C2).
- [`ai-context/references/AGENTIC_PATTERNS.md`](ai-context/references/AGENTIC_PATTERNS.md) — racional técnico dos padrões agentic adotados (Tool Use, Guardrails, Basic RAG, Plan-then-Execute, Human-in-the-Loop).

### Estratégia de orquestração do agente (runtime)

O agente gerado é um **`LlmAgent` único** do Google ADK (não há sub-agentes nem multi-agent hierarchy em runtime). A orquestração acontece por **tool-use sequencial** guiado por `instruction` fixa: o LLM (Gemini 2.5 Flash) recebe o texto mascarado do OCR e decide a ordem das chamadas de tools, mas o contrato de fluxo está ancorado em [ADR-0006](docs/adr/0006-spec-schema-and-agent-topology.md) e formaliza a sequência obrigatória:

```
  --image  ──▶  OCR MCP (tool)  ──▶  PII mask Layer 1
                                            │
                                            ▼
                              PII mask Layer 2 (before_model_callback ADK)
                                            │
                                            ▼
                                    LLM planeja (Gemini)
                                            │
                                            ▼
                          RAG MCP × N (uma chamada por exame)
                                            │
                                            ▼
                        POST /api/v1/appointments (scheduling-api)
                                            │
                                            ▼
                         Tabela ASCII no stdout + exit 0
```

Um único agente, três tools (`extract_exams_from_image`, `search_exam_code`, `list_exams`) mais o `OpenAPIToolset` da scheduling-api. Detalhe completo do fluxo — incluindo tratamento de falhas parciais, dupla camada PII e correlação via `correlation_id` — em [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) e [`docs/tutorials/05-generated-agent.md`](docs/tutorials/05-generated-agent.md).

### Principais referências consultadas

As decisões arquiteturais deste projeto se ancoram em documentação oficial e literatura técnica rastreável. As fontes mais load-bearing:

- [Google ADK documentation](https://google.github.io/adk-docs/) — `LlmAgent`, `McpToolset`, `SseConnectionParams`, `before_model_callback` (ADR-0006; ver ADR-0001 § Correção da correção 2026-04-19).
- [Model Context Protocol specification](https://modelcontextprotocol.io/) e [Python SDK (FastMCP)](https://github.com/modelcontextprotocol/python-sdk) — transporte SSE e shape das tools (ADR-0001).
- [Microsoft Presidio](https://microsoft.github.io/presidio/) + documentação de custom recognizers — base da camada PII e dos 4 recognizers BR (ADR-0003).
- [GitHub `spec-kit`](https://github.com/github/spec-kit) — metodologia SDD adaptada para este projeto (ADR-0004).
- [Google AI — Gemini API](https://ai.google.dev/) — modelo `gemini-2.5-flash`, estrutura de `contents`/`parts` (ADR-0005).
- [SIGTAP / DATASUS](http://sigtap.datasus.gov.br/) — catálogo público de nomenclatura médica brasileira usado pelo RAG (ADR-0007).
- Livros consultados para padrões agentic: *Agentic Design Patterns* (A. Gulli), *AI Engineering* (Chip Huyen), *Building Generative AI Services with FastAPI* (V. Lakshmanan).

Lista completa, agrupada por domínio e ancorada em cada ADR, em [`docs/REFERENCES.md`](docs/REFERENCES.md). Log bruto de toda fonte consultada durante o desenvolvimento — inclusive descobertas que não viraram código — em [`ai-context/LINKS.md`](ai-context/LINKS.md).

### Commits contam história

O log de git é intencionalmente auditável: commits são pequenos, em Conventional Commits em inglês, citam o ID da task (`Txxx`) ou do critério de aceitação (`ACn`) que fecham, e são ordenados para comunicar a evolução do software — não são dumps de "work in progress". `git log --oneline` revela a trilha bloco a bloco.

### Declaração clara

Este projeto foi co-construído com Claude Code (Anthropic) como assistente de engenharia. Decisões de arquitetura, ADRs, e aprovação de cada spec/plan/tasks foram feitas pelo autor humano; implementação, testes e documentação foram geradas/editadas pela IA sob direção humana. Nenhum bloco foi aceito sem revisão independente do `code-reviewer` (Opus) e aprovação explícita do usuário no checkpoint #2.

## Licença / Autoria

Projeto entregue como parte do Desafio Técnico Sênior IA.

Autor: Filipe Andrade — filipeandrade.work@gmail.com.

Código sob licença MIT (ver `LICENSE` quando adicionado). Os catálogos de nomenclatura médica (SIGTAP) em `rag_mcp/rag_mcp/data/exams.csv` são de domínio público (Ministério da Saúde — DATASUS).
