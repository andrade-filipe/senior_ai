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
- [oficial] https://adk.dev/tools-custom/mcp-tools/ — classe `McpToolset` + `StreamableHTTPConnectionParams` (ADR-0001, ADR-0006).
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
- [oficial] https://docs.astral.sh/uv/concepts/projects/ — `pyproject.toml` por projeto + `uv.lock`.
- [oficial] https://docs.astral.sh/uv/concepts/projects/workspaces/ — workspaces (opcional — auditoria 2026-04 confirmou viabilidade como melhoria futura; ver `DESIGN_AUDIT.md` C8).
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

## Outras

*(uso pontual — marcar com `[util]`)*
