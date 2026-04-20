# LINKS — Referências usadas

Log vivo de **toda fonte externa** consultada durante o desafio.
Se usamos uma URL, um paper, um artigo ou um vídeo para decidir algo ou produzir qualquer artefato do repositório, ela entra aqui.

## Como usar este arquivo

- **Adicionar** sempre que consultar uma fonte nova. Não postergue — esquecer quebra a rastreabilidade.
- **Citar** o link no artefato que usa a informação (comentário no código, seção de referências em `docs/ARCHITECTURE.md`, ADR, etc.) **E** listar aqui.
- **Organizar** por área, não cronológico. Dentro de cada área, ordenar por utilidade.
- **Marcar** com anotação curta:
  - `[oficial]` documentação mantida pelo autor da lib/serviço.
  - `[blog]` post em blog/empresa.
  - `[codelab]` tutorial guiado oficial.
  - `[ref]` referência técnica (RFC, paper, especificação).
  - `[util]` útil durante a pesquisa; pode não ter virado código.
- **Remover** se virar irrelevante (ex.: doc oficial migrou de URL) — substituir pela nova.

## Google ADK (Agent Development Kit)

- [oficial] https://adk.dev/ — documentação oficial (domínio migrou de `google.github.io/adk-docs/` para `adk.dev/` — confirmado em 2026-04-18).
- [oficial] https://adk.dev/agents/llm-agents/ — referência para `LlmAgent` usado em ADR-0006 (parâmetro é `instruction` singular).
- [oficial] https://adk.dev/tools-custom/mcp-tools/ — classe `McpToolset` + `SseConnectionParams` (ADR-0001 § Correção da correção 2026-04-19; `StreamableHTTPConnectionParams` fala outro protocolo).
- [source-of-truth] `google/adk/tools/mcp_tool/mcp_session_manager.py:89,120,400,408` (google-adk==1.31.0) — confirma `SseConnectionParams` pública e dispatch para `sse_client()` legado; é a única classe compatível com FastMCP `transport="sse"` no nosso stack.
- [oficial] https://adk.dev/callbacks/ — `before_model_callback(callback_context, llm_request)` (ADR-0003).
- [oficial] https://github.com/google/adk-python — repositório oficial, fonte canônica para imports.
- [codelab] https://codelabs.developers.google.com/your-first-agent-with-adk?hl=pt-br#0 — primeiro agente ADK.
- [blog] https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/ — anúncio e high-level.

## MCP (Model Context Protocol) e FastMCP

- [oficial] https://modelcontextprotocol.io/ — spec e conceitos do protocolo.
- [oficial] https://modelcontextprotocol.io/docs/concepts/transports — transports (stdio, SSE, Streamable HTTP) — base da ADR-0001.
- [oficial] https://github.com/modelcontextprotocol/python-sdk — SDK Python oficial (`mcp[cli]`).
- [oficial] https://github.com/jlowin/fastmcp — FastMCP (abstração sobre o SDK, usada pelos servidores OCR/RAG).

## FastAPI e Pydantic v2

- [oficial] https://fastapi.tiangolo.com/ — documentação FastAPI.
- [oficial] https://docs.pydantic.dev/latest/ — Pydantic v2; usada para `AgentSpec` (ADR-0006) e schemas da scheduling-api.
- [oficial] https://fastapi.tiangolo.com/tutorial/response-model/ — `response_model` obrigatório por rota (GUIDELINES §3).

## Microsoft Presidio e reconhecedores PT-BR

- [oficial] https://microsoft.github.io/presidio/ — documentação Presidio (analyzer + anonymizer).
- [oficial] https://microsoft.github.io/presidio/supported_entities/ — lista oficial de entidades suportadas; confirma que **Brasil não está coberto** (auditoria 2026-04-18) → BR recognizers são custom.
- [oficial] https://github.com/microsoft/presidio — repositório oficial.
- [ref] https://github.com/microsoft/presidio/tree/main/presidio-analyzer/presidio_analyzer/predefined_recognizers — recognizers nativos, template para escrever BR_CPF/BR_CNPJ/BR_RG/BR_PHONE do zero.
- [ref] https://github.com/matheuscas/pycpfcnpj — validação de dígitos verificadores CPF/CNPJ; usado dentro dos custom recognizers BR.
- [oficial] https://spacy.io/models/pt — `pt_core_news_lg` usado como NLP engine do Presidio em PT-BR.

## Jinja2 e geração de código Python

- [oficial] https://jinja.palletsprojects.com/ — documentação Jinja2; usada pelo transpilador (ADR-0002).
- [oficial] https://docs.python.org/3/library/ast.html — módulo `ast` da stdlib; `ast.parse()` como gate de correção no transpilador.
- [ref] https://jinja.palletsprojects.com/en/stable/api/#jinja2.Environment — `trim_blocks`, `lstrip_blocks`, `autoescape=False` para geração de código (GUIDELINES).

## rapidfuzz (RAG MCP)

- [oficial] https://github.com/rapidfuzz/RapidFuzz — repo oficial; usado no ADR-0007.
- [oficial] https://maxbachmann.github.io/RapidFuzz/ — documentação; referência para `process.extractOne` + scorers `WRatio`.

## Docker e Compose

- [oficial] https://docs.docker.com/compose/ — Compose v2.
- [oficial] https://docs.docker.com/compose/compose-file/ — referência do arquivo `docker-compose.yml` (healthchecks, `depends_on.condition`).
- [oficial] https://docs.astral.sh/uv/guides/integration/docker/ — guia oficial `uv` + Docker, base para os Dockerfiles (ADR-0005).

## uv (gerenciador de dependências)

- [oficial] https://docs.astral.sh/uv/ — documentação oficial.
- [oficial] https://docs.astral.sh/uv/getting-started/installation/ — métodos de instalação (winget, PowerShell installer, pip); base do `ai-context/references/ENV_SETUP.md`.
- [oficial] https://docs.astral.sh/uv/guides/install-python/ — `uv python install <version>` para gerenciar Python isolado; usado para trazer 3.12 sem poluir o sistema.
- [oficial] https://docs.astral.sh/uv/concepts/projects/ — `pyproject.toml` por projeto + `uv.lock`.
- [oficial] https://docs.astral.sh/uv/concepts/projects/workspaces/ — workspaces (opcional — auditoria 2026-04 confirmou viabilidade como melhoria futura; ver `DESIGN_AUDIT.md` C8).
- [ref] https://github.com/astral-sh/python-build-standalone — distribuição Python standalone que o uv usa internamente em `uv python install`.
- [blog] https://astral.sh/blog/uv — anúncio e motivação.

## Google Gemini (LLM)

- [oficial] https://ai.google.dev/gemini-api/docs — documentação da API.
- [oficial] https://ai.google.dev/gemini-api/docs/models — matriz de modelos; em 2026-04, `gemini-2.5-flash` é o stable recomendado (ADR-0005). `gemini-2.0-flash` está marcado como deprecated.
- [oficial] https://ai.google.dev/gemini-api/docs/quickstart — quickstart com API key (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`).
- [oficial] https://adk.dev/get-started/quickstart/#gemini---google-ai-studio — integração ADK ↔ Gemini API key.

## GitHub Actions (CI)

- [oficial] https://docs.github.com/actions — documentação geral Actions.
- [oficial] https://docs.github.com/actions/using-workflows — estrutura de workflows (usado em `.github/workflows/ci.yml`, ADR-0005).
- [ref] https://docs.astral.sh/uv/guides/integration/github/ — recomendações oficiais `uv` + Actions.

## Spec-Driven Development (SDD)

- [oficial] https://github.com/github/spec-kit — spec-kit do GitHub; inspiração direta para ADR-0004 e templates em `docs/specs/README.md`.
- [ref] https://github.com/github/spec-kit/blob/main/spec-driven.md — manifesto SDD; regra de ouro "specs não servem ao código; o código serve às specs".
- [blog] https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/ — introdução ao spec-kit no blog GitHub.
- [ref] https://martinfowler.com/articles/exploring-gen-ai/sdd-tools.html — análise de Martin Fowler sobre ferramentas SDD.

## Agentic patterns (livros e artigos — pesquisa 2026-04-18)

Pesquisa consolidada em [`references/AGENTIC_PATTERNS.md`](references/AGENTIC_PATTERNS.md). Livros pagos; consultamos índices, amostras, reviews e posts complementares dos autores.

- [ref] https://www.packtpub.com/en-us/product/agentic-design-patterns-9781836200628 — Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (Packt, 2025). Fonte de: Reflection, Tool Use, Planning, Multi-Agent Collaboration, Orchestrator-Worker.
- [ref] https://www.oreilly.com/library/view/ai-engineering/9781098166298/ — Chip Huyen, *AI Engineering: Building Applications with Foundation Models* (O'Reilly, 2025). Fonte de: plataforma GenAI em camadas, classificação de tools (knowledge/capability/write-action), stream completion risk, guardrails.
- [blog] https://huyenchip.com/2025/01/07/agents.html — post "Agents" de Chip Huyen (janeiro 2025); complementar ao livro, trata patterns de agent failure.
- [blog] https://huyenchip.com/2024/07/25/genai-platform.html — post "Building A Generative AI Platform" (julho 2024); estrutura de camadas adotada no `ARCHITECTURE.md § Camadas conscientemente omitidas`.
- [ref] https://www.oreilly.com/library/view/generative-ai-design/9781098182014/ — Valliappa Lakshmanan & Hannes Hapke, *Generative AI Design Patterns: Solutions to Common Challenges When Building GenAI Agents and Applications* (O'Reilly, 2025). Fonte de: Basic RAG, Assembled Reformat, Trustworthy Generation com citations, LLM-as-Judge, Dependency Injection, Guardrails.
- [blog] https://www.sitepoint.com/ai-agent-design-patterns-2026/ — SitePoint 2026, síntese prática de padrões agentic (referência cruzada para o glossário).
- [blog] https://machinelearningmastery.com/agentic-ai-roadmap-2026/ — Machine Learning Mastery, roadmap 2026 de agentic AI (util para priorizar backlog de Bloco 6).
- [util] tweet @AndrewYNg (2025): "agentic workflows > bigger models" — justificativa para focar em patterns em vez de trocar modelo.

## Catálogos de nomenclatura médica (BR)

Fontes públicas consideradas para popular o CSV do RAG MCP (ADR-0007 § "Fonte do dataset"). Restrição absoluta: zero dados de paciente — apenas nomenclatura e códigos.

- [oficial] https://datasus.saude.gov.br/sigtap/ — portal SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos do SUS / DATASUS). **Fonte primária** escolhida: ≥ 4.600 procedimentos SUS, domínio público (LAI), atualizado mensalmente, distribuído como `.txt` fixed-width.
- [ref] https://github.com/rdsilva/SIGTAP — conversão comunitária do SIGTAP para CSV (licença MIT). Aceitável como conveniência se derivação do `.txt` oficial virar fricção; registrar URL + data no commit.
- [oficial] https://dados.gov.br/ — portal de dados abertos do governo federal; hospeda distribuição do rol ANS/TUSS como **fallback** quando SIGTAP não cobre um exame específico.
- [oficial] https://www.gov.br/ans/pt-br/acesso-a-informacao/participacao-da-sociedade/atualizacao-do-rol-de-procedimentos — ANS, rol de procedimentos (TUSS) — saúde suplementar, fallback para bioquímica mais granular.
- [ref] https://loinc.org/international/brazil/ — LOINC PT-BR. **REJEITADO** (ADR-0007): licença Regenstrief com cláusulas de redistribuição controlada + overkill para MVP (60–70k termos vs ≥ 120 necessários).

**Uso no Bloco 0003** (data de acesso: 2026-04-19): o catálogo `rag_mcp/data/exams.csv` foi criado manualmente derivando nomenclaturas e categorias de exames laboratoriais e de imagem comuns da tabela SIGTAP. Os nomes canônicos, categorias clínicas (hematologia, bioquímica, hormônios, etc.) e siglas comuns (aliases) foram baseados na nomenclatura do SUS (SIGTAP/DATASUS) e do rol ANS/TUSS. Nenhum dado de paciente incluído — apenas nomenclatura pública de procedimentos. Fonte primária: https://datasus.saude.gov.br/sigtap/ | Fallback verificado: https://dados.gov.br/ | Licença: domínio público (LAI).

## Design by Contract (DbC)

Bases teóricas + ferramentas concretas para a disciplina declarada em `ai-context/GUIDELINES.md § 10` e aplicada na seção "Design by Contract" de cada `docs/specs/NNNN-<slug>/plan.md`.

- [oficial] https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html — Google-style docstrings (Sphinx Napoleon). Formato adotado para seções `Pre`, `Post`, `Invariant`, `Raises`.
- [ref] https://peps.python.org/pep-0316/ — PEP 316 "Programming by Contract for Python" (histórico; rejeitado oficialmente mas referência do vocabulário `pre`/`post`/`invariant`).
- [oficial] https://docs.pydantic.dev/latest/concepts/validators/ — Pydantic v2 `field_validator` / `model_validator`. Cobre pré-condição de dados sem lib extra.
- [util] https://github.com/Parquery/icontract — `icontract` lib (avaliada e **descartada**: overhead runtime + dep nova em 3 serviços + redundância com Pydantic v2).

## Clean Code (Python procedural)

Referências que fundamentam o bloco "Critérios Clean Code (Python procedural)" de `.claude/agents/code-reviewer.md` e `ai-context/GUIDELINES.md § 1.1`. Foco: heurísticas pragmáticas aplicáveis a código procedural/funcional — sem dogmas OOP.

- [ref] https://www.oreilly.com/library/view/clean-code-a/9780136083238/ — *Clean Code: A Handbook of Agile Software Craftsmanship*, Robert C. Martin (2008). Fonte do vocabulário (nomes significativos, funções pequenas, DRY). SOLID e Object Calisthenics explicitamente **dispensados** aqui por serem OOP-centric.
- [ref] https://github.com/zedr/clean-code-python — adaptação comunitária dos princípios Clean Code para Python (util como checklist cruzado).
- [oficial] https://docs.astral.sh/ruff/rules/ — referência de regras do Ruff. Usamos `E, F, I, UP, B, S, C901, SIM, RET, N` (GUIDELINES § 1).
- [ref] https://www.sonarsource.com/docs/CognitiveComplexity.pdf — paper SonarSource sobre Cognitive Complexity. Referenciado mas **não adotado como gate** no MVP (opt-in se `complexipy` entrar no toolchain depois).
- [blog] https://qntm.org/clean — crítica ao dogma "funções de 4–20 linhas" do Uncle Bob. Justifica nossa heurística mais flexível (≤ 25 linhas, com exceções).

## Outras

*(uso pontual — marcar com `[util]`)*
