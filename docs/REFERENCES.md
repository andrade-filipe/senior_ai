# Referências e materiais consultados

Este documento atende ao item 2 da seção "Transparência e Uso de IA" de [`docs/DESAFIO.md`](DESAFIO.md): as principais referências públicas usadas durante o desenvolvimento do desafio. Está organizado por domínio técnico e, ao início de cada seção, explica **quais decisões do projeto foram apoiadas** por aquelas fontes — com ponteiros para as ADRs correspondentes em [`docs/adr/`](adr/README.md).

O log operacional completo (incluindo notas internas de pesquisa e utilitários de busca) permanece em `ai-context/LINKS.md`; aqui preservamos somente as fontes primárias que sustentam decisões arquiteturais e o código entregue.

---

## 1. Google ADK (Agent Development Kit)

O ADK é o framework de agentes imposto pelo desafio. Todas as decisões sobre topologia do agente ([ADR-0006](adr/0006-spec-schema-and-agent-topology.md)), integração com MCP ([ADR-0001](adr/0001-mcp-transport-sse.md)) e a dupla camada de PII via `before_model_callback` ([ADR-0003](adr/0003-pii-double-layer.md)) foram ancoradas na documentação oficial. A auditoria pré-implementação de 2026-04-18 identificou dois ajustes factuais a partir dessas fontes: o domínio oficial migrou de `google.github.io/adk-docs/` para `adk.dev/`, e o nome correto da classe cliente passou a ser `McpToolset` (com `StreamableHTTPConnectionParams` em vez do extinto `SseConnectionParams`).

- https://adk.dev/ — documentação oficial.
- https://adk.dev/agents/llm-agents/ — referência de `LlmAgent` (parâmetro `instruction` singular, usado no template Jinja2 do transpilador).
- https://adk.dev/tools-custom/mcp-tools/ — `McpToolset` e `StreamableHTTPConnectionParams`.
- https://adk.dev/callbacks/ — assinatura `before_model_callback(callback_context, llm_request)`, base da PII Layer 2.
- https://adk.dev/get-started/quickstart/#gemini---google-ai-studio — integração com Gemini via API key (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`).
- https://github.com/google/adk-python — repositório oficial.
- https://codelabs.developers.google.com/your-first-agent-with-adk?hl=pt-br#0 — codelab "primeiro agente ADK".
- https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/ — anúncio oficial.

---

## 2. MCP (Model Context Protocol) e FastMCP

O transporte SSE é exigência literal do desafio e está fixado pela [ADR-0001](adr/0001-mcp-transport-sse.md). A especificação oficial do protocolo e a documentação de transportes sustentam a decisão, e o SDK Python `mcp[cli]` é a base dos dois servidores (`ocr-mcp` e `rag-mcp`). A biblioteca FastMCP foi escolhida como abstração concreta por oferecer um `@mcp.tool()` ergonômico com validação de tipo compatível com Pydantic v2.

- https://modelcontextprotocol.io/ — especificação e conceitos.
- https://modelcontextprotocol.io/docs/concepts/transports — referência dos transportes (stdio, SSE, Streamable HTTP).
- https://github.com/modelcontextprotocol/python-sdk — SDK Python oficial (`mcp[cli]`).
- https://github.com/jlowin/fastmcp — abstração FastMCP.

---

## 3. FastAPI e Pydantic v2

A API de agendamento ([Bloco 0004](specs/)) e a validação do `AgentSpec` do transpilador ([Bloco 0001](specs/), [ADR-0006](adr/0006-spec-schema-and-agent-topology.md)) dependem integralmente de Pydantic v2 e FastAPI. As regras de `response_model` obrigatório por rota (aplicadas pelo `code-reviewer` via `ai-context/GUIDELINES.md § 3`) vêm do tutorial oficial; o shape canônico de erro (`{error: {code, message, hint, path, context}, correlation_id}`) especificado em [ADR-0008](adr/0008-robust-validation-policy.md) foi implementado sobrescrevendo o default `{"detail": ...}` com `exception_handler`s.

- https://fastapi.tiangolo.com/ — documentação FastAPI.
- https://fastapi.tiangolo.com/tutorial/response-model/ — `response_model` por rota.
- https://docs.pydantic.dev/latest/ — Pydantic v2.
- https://docs.pydantic.dev/latest/concepts/validators/ — `field_validator` e `model_validator`, usados tanto em `AgentSpec` quanto nos schemas da API. Cobrem pré-condições de dados sem biblioteca adicional (a lib `icontract` chegou a ser avaliada e descartada — ver seção "Design by Contract").

---

## 4. Microsoft Presidio e reconhecedores PT-BR

A camada PII ([Bloco 0005](specs/), [ADR-0003](adr/0003-pii-double-layer.md)) usa Presidio como motor. A auditoria de 2026-04-18 confirmou, pelas fontes oficiais abaixo, que Presidio **não oferece reconhecedores brasileiros nativos** — `BR_CPF`, `BR_CNPJ`, `BR_RG` e `BR_PHONE` foram escritos neste projeto, usando os recognizers predefinidos como template de estrutura e `pycpfcnpj` para checksum de dígitos verificadores. O modelo NLP PT-BR é `pt_core_news_lg` da spaCy.

- https://microsoft.github.io/presidio/ — documentação oficial.
- https://microsoft.github.io/presidio/supported_entities/ — lista oficial de entidades (confirma a ausência de cobertura BR).
- https://github.com/microsoft/presidio — repositório oficial.
- https://github.com/microsoft/presidio/tree/main/presidio-analyzer/presidio_analyzer/predefined_recognizers — recognizers nativos usados como template.
- https://github.com/matheuscas/pycpfcnpj — validação de CPF/CNPJ por dígito verificador.
- https://spacy.io/models/pt — modelo `pt_core_news_lg`.

---

## 5. Jinja2 e geração de código Python

O transpilador ([Bloco 0002](specs/), [ADR-0002](adr/0002-transpiler-jinja-ast.md)) renderiza o pacote `generated_agent/` a partir de templates Jinja2 e valida cada arquivo gerado com `ast.parse()` da stdlib como *gate* de correção sintática. A configuração do `Environment` (`trim_blocks`, `lstrip_blocks`, `autoescape=False`) segue diretamente a recomendação da documentação Jinja para geração de código (não HTML).

- https://jinja.palletsprojects.com/ — documentação Jinja2.
- https://jinja.palletsprojects.com/en/stable/api/#jinja2.Environment — parâmetros do `Environment` para geração de código.
- https://docs.python.org/3/library/ast.html — módulo `ast` da stdlib.

---

## 6. rapidfuzz (RAG)

O MCP de RAG ([Bloco 0003](specs/), [ADR-0007](adr/0007-rag-fuzzy-and-catalog.md)) usa `rapidfuzz.process.extractOne` com scorer `WRatio` sobre o catálogo CSV. O threshold 80/100 foi fixado depois de calibração contra aliases reais (`HMG`, `HEMO`, `HEMOGRAMA COMPLETO`) — abaixo disso, `search_exam_code` retorna `null` e o agente recorre a `list_exams(limit=20)`.

- https://github.com/rapidfuzz/RapidFuzz — repositório oficial.
- https://maxbachmann.github.io/RapidFuzz/ — documentação; referência de `process.extractOne` e dos scorers.

---

## 7. Docker e Docker Compose

A contentorização ([Bloco 0007](specs/)) usa exclusivamente Docker e um `docker-compose.yml` na raiz. Os quatro `Dockerfile`s seguem o guia oficial `uv + Docker` (imagem base `python:3.12-slim`, `uv pip install --system`, `CMD` em forma exec). `HEALTHCHECK` em todos os serviços HTTP, `depends_on.condition: service_healthy` para a API e `service_started` para os MCPs (SSE não tem healthcheck trivial — ver nota final da [ADR-0001](adr/0001-mcp-transport-sse.md)).

- https://docs.docker.com/compose/ — Compose v2.
- https://docs.docker.com/compose/compose-file/ — referência do arquivo (healthchecks, `depends_on.condition`).
- https://docs.astral.sh/uv/guides/integration/docker/ — guia oficial `uv` + Docker.

---

## 8. uv (gerenciamento de dependências e Python)

O `uv` é o gerenciador único de dependências e de versão de Python, fixado pela [ADR-0005](adr/0005-dev-stack.md). Cada serviço tem um `pyproject.toml` próprio (sem pyproject na raiz); as dev dependencies vivem em `[dependency-groups]` (PEP 735) para que `uv sync` instale tudo por default. O Python 3.12 é trazido via `uv python install 3.12` sem poluir o sistema host.

- https://docs.astral.sh/uv/ — documentação oficial.
- https://docs.astral.sh/uv/getting-started/installation/ — instalação.
- https://docs.astral.sh/uv/guides/install-python/ — `uv python install`.
- https://docs.astral.sh/uv/concepts/projects/ — `pyproject.toml` por projeto e `uv.lock`.
- https://docs.astral.sh/uv/concepts/projects/workspaces/ — workspaces (avaliado e deferido para futuro).
- https://github.com/astral-sh/python-build-standalone — distribuição Python standalone subjacente.
- https://astral.sh/blog/uv — anúncio oficial.

---

## 9. Google Gemini (LLM)

O modelo único do sistema é `gemini-2.5-flash`, fixado como `Literal` no schema `AgentSpec` e em [ADR-0005](adr/0005-dev-stack.md). Usa-se a API direta (Google AI Studio) com `GOOGLE_GENAI_USE_VERTEXAI=FALSE`. A auditoria pré-implementação confirmou, na matriz oficial de modelos, que `gemini-2.0-flash` está deprecated em 2026-04 e que 2.5-flash é o stable recomendado.

- https://ai.google.dev/gemini-api/docs — documentação da API.
- https://ai.google.dev/gemini-api/docs/models — matriz de modelos.
- https://ai.google.dev/gemini-api/docs/quickstart — quickstart com API key.

---

## 10. GitHub Actions (CI)

O CI mínimo (`.github/workflows/ci.yml`) é parte da stack fechada da [ADR-0005](adr/0005-dev-stack.md). O workflow roda `ruff check`, `ruff format --check`, `mypy`, `pytest --cov --cov-fail-under=80` e `docker build` a cada push/PR. A recomendação oficial `uv + Actions` é seguida para cache e setup do interpretador.

- https://docs.github.com/actions — documentação geral.
- https://docs.github.com/actions/using-workflows — estrutura de workflows.
- https://docs.astral.sh/uv/guides/integration/github/ — integração `uv` + Actions.

---

## 11. Spec-Driven Development

O método de trabalho (spec → plan → tasks → checkpoint #1 → testes → código → review → evidência → checkpoint #2) está fixado em [ADR-0004](adr/0004-sdd-tdd-workflow.md) e detalhado em [`ai-context/WORKFLOW.md`](../ai-context/WORKFLOW.md). A inspiração direta foi o `spec-kit` do GitHub, cujo manifesto resumiu a regra de ouro adotada ("specs não servem ao código; o código serve às specs"). A análise de Martin Fowler sobre ferramentas SDD ajudou a calibrar quando o ciclo vale o overhead versus quando "same-commit" é suficiente — daí a distinção pragmática entre test-first obrigatório (transpilador, security) e same-commit (MCPs, API, infra).

- https://github.com/github/spec-kit — spec-kit oficial.
- https://github.com/github/spec-kit/blob/main/spec-driven.md — manifesto SDD.
- https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/ — introdução no blog do GitHub.
- https://martinfowler.com/articles/exploring-gen-ai/sdd-tools.html — análise de Martin Fowler.

---

## 12. Padrões agentic (livros e artigos)

A estrutura do `LlmAgent` único com plano fixo (`plan-then-execute`), a classificação das tools (knowledge vs write-action) e as camadas conscientemente omitidas (Router, Cache semântico) em [`docs/ARCHITECTURE.md § Camadas conscientemente omitidas`](ARCHITECTURE.md#camadas-conscientemente-omitidas) são embasadas diretamente nas referências abaixo. Os livros foram consultados via índices e amostras públicas; os posts dos autores complementam os tópicos mais operacionais.

- https://www.packtpub.com/en-us/product/agentic-design-patterns-9781836200628 — Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (Packt, 2025). Fonte dos padrões Reflection, Tool Use, Planning, Multi-Agent Collaboration e Orchestrator-Worker.
- https://www.oreilly.com/library/view/ai-engineering/9781098166298/ — Chip Huyen, *AI Engineering: Building Applications with Foundation Models* (O'Reilly, 2025). Fonte do modelo de plataforma GenAI em camadas e da taxonomia de tools adotada.
- https://huyenchip.com/2025/01/07/agents.html — post "Agents" de Chip Huyen (jan/2025); complementa o livro com padrões de falha.
- https://huyenchip.com/2024/07/25/genai-platform.html — post "Building A Generative AI Platform" (jul/2024); estrutura de camadas adotada parcialmente.
- https://www.oreilly.com/library/view/generative-ai-design/9781098182014/ — Valliappa Lakshmanan & Hannes Hapke, *Generative AI Design Patterns* (O'Reilly, 2025). Fonte de Basic RAG, Assembled Reformat, Trustworthy Generation com citations e Dependency Injection (padrões aplicados na `instruction` do `LlmAgent`).

---

## 13. Catálogos médicos brasileiros (SIGTAP)

O catálogo do RAG MCP ([ADR-0007](adr/0007-rag-fuzzy-and-catalog.md)) deriva de nomenclatura pública brasileira — **zero dados de paciente**, apenas nomes canônicos e códigos de procedimentos. A fonte primária é o SIGTAP (DATASUS), domínio público por LAI. O rol ANS/TUSS foi considerado como fallback para exames de bioquímica mais granulares. O LOINC PT-BR foi avaliado e **rejeitado** pela ADR por questões de licenciamento (redistribuição controlada pela Regenstrief) e por ser excessivo para o MVP.

- https://datasus.saude.gov.br/sigtap/ — portal oficial SIGTAP/DATASUS (fonte primária).
- https://github.com/rdsilva/SIGTAP — conversão comunitária para CSV (MIT) usada como conveniência de derivação.
- https://dados.gov.br/ — portal de dados abertos do governo federal (fallback).
- https://www.gov.br/ans/pt-br/acesso-a-informacao/participacao-da-sociedade/atualizacao-do-rol-de-procedimentos — ANS, rol TUSS (fallback para saúde suplementar).
- https://loinc.org/international/brazil/ — LOINC PT-BR (rejeitado por licença e volume; registrado por transparência).

---

## 14. Design by Contract

Os contratos semânticos declarados em docstrings (`Pre`, `Post`, `Invariant`, `Raises`) e a rastreabilidade tripla "AC ↔ linha DbC ↔ task" em cada `spec.md` / `plan.md` / `tasks.md` são formalizados em [`ai-context/GUIDELINES.md § 10`](../ai-context/GUIDELINES.md). As fontes abaixo sustentam a escolha de manter a disciplina **sem nenhuma biblioteca adicional**: Pydantic v2 cobre pré-condições de dados, `assert` cobre fronteiras críticas e testes cobrem pós-condições e invariantes.

- https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html — Google-style docstrings (formato adotado).
- https://peps.python.org/pep-0316/ — PEP 316 "Programming by Contract for Python" (histórico; rejeitada oficialmente, mas referência do vocabulário `pre`/`post`/`invariant`).
- https://docs.pydantic.dev/latest/concepts/validators/ — `field_validator` / `model_validator` cobrindo pré-condição de dados.

---

## 15. Clean Code (Python procedural)

A seção "Critérios Clean Code (Python procedural)" aplicada pelo `code-reviewer` no checkpoint #2 e resumida em [`ai-context/GUIDELINES.md § 1.1`](../ai-context/GUIDELINES.md) adota um subconjunto pragmático — foco em nomes, funções pequenas, DRY e exceções custom. SOLID e Object Calisthenics são **explicitamente dispensados** (código procedural, não OOP). A heurística de tamanho (≤ 25 linhas por função, não o dogma "4–20 linhas") reconhece a crítica de qntm ao absolutismo do Uncle Bob. O `ruff` é a ferramenta única de lint — sem `pylint`, sem `flake8` — com o conjunto `E, F, I, UP, B, S, C901, SIM, RET, N`.

- https://www.oreilly.com/library/view/clean-code-a/9780136083238/ — Robert C. Martin, *Clean Code* (2008). Fonte do vocabulário adotado.
- https://github.com/zedr/clean-code-python — adaptação comunitária para Python; usada como checklist cruzado.
- https://docs.astral.sh/ruff/rules/ — referência oficial das regras do Ruff.
- https://www.sonarsource.com/docs/CognitiveComplexity.pdf — paper SonarSource sobre Cognitive Complexity (referenciado, não adotado como gate).
- https://qntm.org/clean — crítica ao dogma "funções de 4–20 linhas"; justifica a heurística mais flexível.
