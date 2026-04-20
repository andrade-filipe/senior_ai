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

## Entregáveis do desafio

Mapeamento direto da seção [“O que deve ser entregue”](docs/DESAFIO.md#o-que-deve-ser-entregue) do enunciado para os artefatos no repositório:

| # | Entregável | Onde está |
|---|---|---|
| 1 | **Código-fonte completo** (transpilador, servidores MCP, API FastAPI, configurações Docker) | [`transpiler/`](transpiler/), [`ocr_mcp/`](ocr_mcp/), [`rag_mcp/`](rag_mcp/), [`scheduling_api/`](scheduling_api/), [`security/`](security/), [`generated_agent/`](generated_agent/) + [`docker-compose.yml`](docker-compose.yml) e `Dockerfile` por serviço |
| 2 | **JSON de especificação** de exemplo | [`docs/fixtures/spec.example.json`](docs/fixtures/spec.example.json) — consumido pelo transpilador via `uv run python -m transpiler docs/fixtures/spec.example.json generated_agent` |
| 3 | **Imagem de teste** do pedido médico fictício | [`docs/fixtures/sample_medical_order.png`](docs/fixtures/sample_medical_order.png) — 9469 bytes, sha256 `17c46fa5…`, montada em `/fixtures/` no container `generated-agent` |
| 4 | **README detalhado** com instruções (Docker, transpilador, agente) | este arquivo — [Quickstart](#quickstart) acima; execução isolada do transpilador em [`docs/tutorials/01-transpiler-cli.md`](docs/tutorials/01-transpiler-cli.md); runbook E2E completo com Gemini real em [`docs/runbooks/e2e-manual-gemini.md`](docs/runbooks/e2e-manual-gemini.md) |
| 5 | **Evidências de funcionamento** (logs, CLI, Swagger) | [`docs/EVIDENCE/`](docs/EVIDENCE/) — 11 arquivos (blocos 0001–0011). Destaque para o **primeiro E2E verde end-to-end de 2026-04-20**: [`0009-output-hardening.md § 5`](docs/EVIDENCE/0009-output-hardening.md), [`0010-pre-ocr-invocation.md`](docs/EVIDENCE/0010-pre-ocr-invocation.md) e [`0011-real-ocr-tesseract.md § T092 Run 2`](docs/EVIDENCE/0011-real-ocr-tesseract.md). Swagger exposto em [http://localhost:8000/docs](http://localhost:8000/docs) quando a stack está de pé |

Cobertura acima do escopo mínimo (transparência por ADR-0004): 11 ADRs aceitas em [`docs/adr/`](docs/adr/), 11 specs SDD completas em [`docs/specs/`](docs/specs/), suíte de testes multi-serviço em [`tests/`](tests/) + `<servico>/tests/`, tutoriais focados em [`docs/tutorials/`](docs/tutorials/README.md), catálogo de 115 exames SIGTAP em [`rag_mcp/rag_mcp/data/exams.csv`](rag_mcp/rag_mcp/data/exams.csv).

## Stack

Decisões fechadas em [ADR-0005](docs/adr/0005-dev-stack.md):

- **Python 3.12** + [`uv`](https://docs.astral.sh/uv/) 0.11+ como gerenciador de dependências e runner de comandos (`uv sync`, `uv run`).
- **Pydantic v2** para o schema `AgentSpec` e para todos os modelos HTTP da `scheduling-api`.
- **FastAPI** + **Uvicorn** na API; **FastMCP** (SDK oficial `mcp[cli]`) nos dois servidores MCP, transporte **SSE** ([ADR-0001](docs/adr/0001-mcp-transport-sse.md)).
- **Google ADK** (`google-adk >= 1.0`) no agente gerado, modelo **Gemini 2.5 Flash** via API direta.
- **Microsoft Presidio** + 4 custom recognizers brasileiros (CPF/CNPJ/RG/Phone) com validação de dígito verificador ([ADR-0003](docs/adr/0003-pii-double-layer.md)).
- **Jinja2** + gate `ast.parse` no transpilador ([ADR-0002](docs/adr/0002-transpiler-jinja-ast.md)).
- **rapidfuzz** + catálogo CSV de 115 exames SIGTAP no RAG MCP ([ADR-0007](docs/adr/0007-rag-fuzzy-and-catalog.md)).
- **Tesseract 5** (`tesseract-ocr` + `tesseract-ocr-por` via apt) + `pytesseract` + `Pillow` no OCR MCP ([ADR-0011](docs/adr/0011-real-ocr-via-tesseract.md)) — substituiu o mock por OCR real, mantendo lookup por hash como fast-path de cache.
- **CLI-orchestrated pre-step** ([ADR-0010](docs/adr/0010-preocr-invocation-pattern.md)): a CLI chama o OCR-MCP via `mcp.client.sse.sse_client` **antes** do `runner.run_async`, injetando a lista de exames como texto no prompt — contorna a limitação do SDK `google-genai` de não conseguir encaminhar bytes do `Part.from_bytes` como argumento de function-call.
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
| Consultar decisões arquiteturais | [`docs/adr/`](docs/adr/) — 11 ADRs, índice em [`docs/adr/README.md`](docs/adr/README.md). |
| Verificar evidências de funcionamento por bloco | [`docs/EVIDENCE/`](docs/EVIDENCE/) — 11 arquivos (0001..0011). |
| Ver a evidência do **primeiro E2E verde end-to-end** (2026-04-20) | [`docs/EVIDENCE/0009-output-hardening.md § 5`](docs/EVIDENCE/0009-output-hardening.md) + [`0010-pre-ocr-invocation.md`](docs/EVIDENCE/0010-pre-ocr-invocation.md) + [`0011-real-ocr-tesseract.md § T092 Run 2`](docs/EVIDENCE/0011-real-ocr-tesseract.md). |
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

### Configuração em runtime (ADR-0009)

A superfície de configuração do sistema é documentada em [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) e formalizada na [ADR-0009](docs/adr/0009-runtime-config-via-env.md). O princípio é *"spec define o default, `.env` sobrescreve em runtime para todo parâmetro com legitimidade operacional"*: modelo Gemini, timeouts, limites de tamanho, thresholds de PII e fuzzy match, caminho do catálogo RAG e modelos spaCy são todos tunáveis sem tocar em código. Em particular, o modelo Gemini pode ser trocado editando `GEMINI_MODEL` no `.env` e rodando `docker compose up -d --force-recreate generated-agent` — capacidade motivada pelo incidente de 2026-04-20, em que o `gemini-2.5-flash` com function-calling retornou `HTTP 503` por saturação server-side do pool Google enquanto outros modelos respondiam normalmente. Calibrações Presidio por-recognizer e contratos públicos da API permanecem hardcoded, com justificativa explícita na ADR.

### Evolução pós-entrega inicial (specs 0009, 0010, 0011)

Três ciclos SDD+TDD adicionais foram conduzidos depois da Onda 5 original, motivados por evidências de runs E2E reais — cada um registrado no ciclo completo (spec + plan + tasks + ADR + RED + GREEN + evidência):

- **Spec 0009 — output hardening** ([`docs/specs/0009-output-hardening/`](docs/specs/0009-output-hardening/)): três camadas de tolerância na CLI para lidar com drift de formato do Gemini 2.5 Pro — `_strip_json_fence` para absorver ``` ```json ``` ``` fences indesejados, união discriminada `RunnerSuccess | RunnerError` com exit 4 (`E_AGENT_OUTPUT_REPORTED_ERROR`), validator-pass opcional (`AGENT_VALIDATOR_PASS_ENABLED=false` default) como rede de segurança, e CLI pre-filter que remove placeholders PII (`<LOCATION>`, `<PERSON>`) e bullets residuais (`1. `, `2) `, `a) `) antes de o prompt chegar ao LLM.
- **Spec 0010 — pre-ocr invocation** ([`docs/specs/0010-pre-ocr-invocation/`](docs/specs/0010-pre-ocr-invocation/) + [ADR-0010](docs/adr/0010-preocr-invocation-pattern.md)): o passo 1 do fluxo deixou de ser uma function-call do LLM e virou uma chamada MCP-SSE direta da CLI contra `ocr-mcp:8001` — contornando a limitação documentada em codelabs oficiais do ADK (*"NEVER ask user to provide base64 data"*) de o Gemini fabricar base64 alucinado quando uma tool pede bytes como argumento. Supersede parcial de ADR-0006.
- **Spec 0011 — OCR real via Tesseract** ([`docs/specs/0011-real-ocr-tesseract/`](docs/specs/0011-real-ocr-tesseract/) + [ADR-0011](docs/adr/0011-real-ocr-via-tesseract.md)): substituição do mock determinístico por `pytesseract` + `tesseract-ocr-por`, preservando o dict de hashes como fast-path de cache opcional. Filtro pós-OCR dropa headers (`PEDIDOMEDICO`, `CPF`, `Exames Solicitados`, etc.) e respeita `_MIN_LINE_LEN=5` com allowlist de acrônimos (`TSH`, `HDL`, `T3`…). Supersede parcial de R11.

O **primeiro E2E completamente verde** do desafio (`docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` → exit 0 + `appointment_id=apt-7b3e2f883d48`) foi capturado em 2026-04-20 21:02 UTC e está documentado cruzadamente em [`docs/EVIDENCE/0009-output-hardening.md § 5`](docs/EVIDENCE/0009-output-hardening.md), [`0010-pre-ocr-invocation.md`](docs/EVIDENCE/0010-pre-ocr-invocation.md) e [`0011-real-ocr-tesseract.md § T092 Run 2`](docs/EVIDENCE/0011-real-ocr-tesseract.md). Um deprecation warning cosmético de `authlib.jose` aparece no startup — é transitivo de `google-adk 1.31.0` (a própria `authlib 1.7.0` avisa que se reorganizará para `joserfc` antes de 2.0); nenhuma ação do projeto é requerida.

### Commits contam história

O log de git é intencionalmente auditável: commits são pequenos, em Conventional Commits em inglês, citam o ID da task (`Txxx`) ou do critério de aceitação (`ACn`) que fecham, e são ordenados para comunicar a evolução do software — não são dumps de "work in progress". `git log --oneline` revela a trilha bloco a bloco.

### Declaração clara

Este projeto foi co-construído com Claude Code (Anthropic) como assistente de engenharia. Decisões de arquitetura, ADRs, e aprovação de cada spec/plan/tasks foram feitas pelo autor humano; implementação, testes e documentação foram geradas/editadas pela IA sob direção humana. Nenhum bloco foi aceito sem revisão independente do `code-reviewer` (Opus) e aprovação explícita do usuário no checkpoint #2.

## Licença / Autoria

Projeto entregue como parte do Desafio Técnico Sênior IA.

Autor: Filipe Andrade — filipeandrade.work@gmail.com.

Código sob licença MIT (ver `LICENSE` quando adicionado). Os catálogos de nomenclatura médica (SIGTAP) em `rag_mcp/rag_mcp/data/exams.csv` são de domínio público (Ministério da Saúde — DATASUS).
