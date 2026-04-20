# ADR-0009: Runtime configuration via environment variables

- **Status**: accepted
- **Data**: 2026-04-20
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

O E2E manual de 2026-04-20 (runbook `docs/runbooks/e2e-manual-gemini.md`, T021 do Bloco 0008) passou em **todos** os estágios anteriores e falhou apenas na chamada final ao Gemini: `gemini-2.5-flash` com function-calling retornou `HTTP 503 UNAVAILABLE` três tentativas seguidas, inclusive após o usuário habilitar billing na conta. Diagnóstico via `curl` direto contra `generativelanguage.googleapis.com` provou que a saturação é **server-side** do pool `gemini-2.5-flash`+tools: no mesmo payload, `gemini-2.5-flash-lite`, `gemini-flash-latest` e `gemini-2.5-pro` responderam `200 OK`. O incidente não é bug local — é falta de um *fallback operacional*.

O problema de processo revelado: o modelo estava **hardcoded em dois lugares** — `generated_agent/agent.py` emitido pelo template, e o `Literal["gemini-2.5-flash"]` em `transpiler/transpiler/schema.py` (congelado por ADR-0006). Trocar o modelo exigia editar código, regenerar o agente via transpilador e reconstruir a imagem. Em produção, isso significa que um time de ops **não consegue reagir** a uma saturação temporária do pool sem participação do time de desenvolvimento.

A mesma pergunta vale para cada constante de runtime espalhada pelo repositório: timeouts, limites de tamanho, thresholds de fuzzy match, score mínimo do Presidio, caminho do catálogo RAG, modelos spaCy. Uma varredura completa identificou 43 valores. O usuário rejeitou a proposta inicial de *"top 10 env vars mais úteis"* — o critério de corte não é volume, é legitimidade operacional. Cada valor precisa ser avaliado caso-a-caso por: *"um operador razoável, um avaliador conduzindo o E2E do desafio, ou um engenheiro de segurança **pode legitimamente** querer mudar isto sem um rebuild?"* Se a resposta é sim, vira env. Se a resposta é *"não, isto é contrato público da API ou calibração algorítmica interna"*, permanece hardcoded — e a ADR precisa dizer **por quê**.

O princípio que passa a valer, codificado aqui: **o spec define o default; o `.env` sobrescreve em runtime para todo parâmetro que tenha legitimidade operacional. Contratos arquiteturais e calibrações algorítmicas internas permanecem hardcoded, com justificativa explícita.**

## Alternativas consideradas

1. **Spec-only** — manter todos os valores no JSON spec e no código; qualquer mudança exige regenerar o `generated_agent/` via transpilador e reconstruir a imagem Docker.
   - Prós: fonte única da verdade; nada de drift entre env e spec; snapshot de configuração versionável no git.
   - Contras: **bloqueia completamente** a resposta ao incidente 503; obriga pipeline CI para cada tuning (threshold, timeout) que não é mudança semântica; operador sem acesso ao código fica paralisado.
   - **Rejeitada**.

2. **Env-everywhere**, incluindo calibrações internas — expor como env também os `score_threshold` por recognizer (CPF=0.85, RG=0.5), `max_length` dos Pydantic schemas da API, portas internas dos containers, tamanhos de `lru_cache`.
   - Prós: máxima flexibilidade ad-hoc; nenhum rebuild é jamais necessário.
   - Contras: (a) calibrações Presidio são **acopladas** — alterar `_SCORE_INVALID=0.1` sem recalcular `PII_SCORE_THRESHOLD=0.5` quebra a semântica (ex.: CPF inválido em contexto dá score 0.45, abaixo do threshold — isso **é o design**, não um bug); mis-config trivial vira pegadinha de produção. (b) `max_length` do Pydantic da API é **contrato público** — mudar por env sem atualizar `/docs` e sem coordenar com o cliente do agente quebra integração externa. (c) portas internas acoplam-se a três lugares (Dockerfile `EXPOSE`, `docker-compose.yml`, URLs dos clientes) sem ganho operacional real. Expor estes três blocos convida configurações inválidas e destrói a disciplina do contrato congelado.
   - **Rejeitada**.

3. **Híbrido com lista explícita** — separar parâmetros por critério operacional: ops→env; contratos/calibrações→hardcoded. Cada item da lista HARDCODED carrega justificativa na própria ADR. Padrão `os.environ.get("VAR", default)` em todo o runtime; o `.env.example` documenta a superfície inteira; `docs/CONFIGURATION.md` dá a visão do operador.
   - Prós: resposta imediata ao 503 (trocar `GEMINI_MODEL` no `.env` + `docker compose up -d --force-recreate`); preserva contratos públicos; dá ao `code-reviewer` e ao guard de testes uma lista fechada contra a qual validar PRs futuros; mantém ADR-0006 e ADR-0008 intactos no que diz respeito a contratos.
   - Contras: superfície maior de documentação (26 vars no `.env.example`, tabelas em `CONFIGURATION.md`); exige supersessão parcial de ADR-0006 no escopo do campo `model`.
   - **Escolhida**.

## Decisão

Adota-se o modelo híbrido. As duas tabelas abaixo são normativas — mudanças exigem PR que atualize esta ADR antes de tocar código.

### Tabela 1 — ENV (26 parâmetros do runtime + 7 do transpilador)

Parâmetros com legitimidade operacional reconhecida. Padrão de leitura: `os.environ.get("VAR", "default-literal")` dentro do próprio módulo; o default reproduz o comportamento anterior à ADR.

#### Runtime do compose (26 — documentados em `.env.example`)

| # | Variável | Arquivo fonte | Default | Justificativa operacional |
|---|---|---|---|---|
| 1 | `GOOGLE_API_KEY` | `generated_agent/agent.py` | `<sem default>` | Chave de API do Gemini; obrigatória, nunca deve ter default público. |
| 2 | `GOOGLE_GENAI_USE_VERTEXAI` | `generated_agent/agent.py` | `FALSE` | Alterna entre Gemini direct API e Vertex AI; operador de infra decide. |
| 3 | `GEMINI_MODEL` | `generated_agent/agent.py` | `gemini-2.5-flash-lite` | **Motivador direto do ADR** — troca de modelo quando o pool do atual está saturado (incidente 503 de 2026-04-20). |
| 4 | `AGENT_TIMEOUT_SECONDS` | `generated_agent/__main__.py` | `300` | Cold-start do Gemini varia; máquinas lentas precisam de mais folga. |
| 5 | `SCHEDULING_OPENAPI_FETCH_TIMEOUT_SECONDS` | `generated_agent/agent.py` | `10` | Fetch do OpenAPI no boot do agente; latência de rede entre containers varia. |
| 6 | `OCR_MCP_URL` | `generated_agent/agent.py` | `http://ocr-mcp:8001/sse` | URL resolvida via DNS do compose; operador pode apontar para MCP externo em testes. |
| 7 | `RAG_MCP_URL` | `generated_agent/agent.py` | `http://rag-mcp:8002/sse` | Idem. |
| 8 | `SCHEDULING_OPENAPI_URL` | `generated_agent/agent.py` | `http://scheduling-api:8000/openapi.json` | Idem. |
| 9 | `OCR_IMAGE_MAX_BYTES` | `ocr_mcp/ocr_mcp/server.py` | `5242880` (5 MB) | Avaliador pode testar com foto real de celular (10 MB+). |
| 10 | `OCR_TIMEOUT_SECONDS` | `ocr_mcp/ocr_mcp/server.py` | `5` | Variação de carga do subprocess Tesseract em hardware diferente. |
| 11 | `OCR_DEFAULT_LANGUAGE` | `ocr_mcp/ocr_mcp/server.py` | `pt` | Suportar entrada em EN sem recompilar. |
| 12 | `RAG_QUERY_MAX_CHARS` | `rag_mcp/rag_mcp/server.py` | `500` | Depende do catálogo e do tamanho típico de prompt. |
| 13 | `RAG_SEARCH_TIMEOUT_SECONDS` | `rag_mcp/rag_mcp/server.py` | `2` | Catálogo maior eleva o tempo de fuzzy match. |
| 14 | `RAG_FUZZY_THRESHOLD` | `rag_mcp/rag_mcp/catalog.py` | `80` | Precisão/recall do match; tuning clássico quando se troca o catálogo. |
| 15 | `RAG_CATALOG_PATH` | `rag_mcp/rag_mcp/server.py` | `/app/rag_mcp/rag_mcp/data/exams.csv` | Trocar catálogo para demo/test/prod sem reconstruir a imagem. |
| 16 | `SCHEDULING_BODY_SIZE_LIMIT_BYTES` | `scheduling_api/scheduling_api/app.py` | `262144` (256 KB) | Batches maiores de exames em cenários de carga. |
| 17 | `SCHEDULING_REQUEST_TIMEOUT_SECONDS` | `scheduling_api/scheduling_api/app.py` | `10` | SLO operacional ajustável por ambiente. |
| 18 | `PII_DEFAULT_LANGUAGE` | `security/security/engine.py` | `pt` | Idioma default do Presidio quando chamador não especifica. |
| 19 | `PII_TEXT_MAX_BYTES` | `security/security/guard.py` | `102400` (100 KB) | Texto longo em iteração de desenvolvimento. |
| 20 | `PII_CALLBACK_TEXT_MAX_BYTES` | `security/security/callback.py` | `102400` | Mesmo cap, superfície diferente (prompt parts). |
| 21 | `PII_ALLOW_LIST_MAX` | `security/security/guard.py` | `1000` | Allow-list custom maior em produção. |
| 22 | `PII_TIMEOUT_SECONDS` | `security/security/guard.py` | `5` | Texto grande ou extraction complexa pode exceder 5 s em máquinas lentas. |
| 23 | `PII_SCORE_THRESHOLD` | `security/security/guard.py` | `0.5` | Segurança ajusta FP/FN global do Presidio; dial canônico de tuning. |
| 24 | `PII_SPACY_MODEL_PT` | `security/security/engine.py` + Dockerfiles (build-arg) | `pt_core_news_lg` | Trocar para `pt_core_news_sm` em máquinas com pouca memória. **Coordenado com Dockerfile** via `ARG PII_SPACY_MODEL_PT` — exige `docker compose build` para re-bake. |
| 25 | `PII_SPACY_MODEL_EN` | `security/security/engine.py` | `en_core_web_lg` | Idem. |
| 26 | `LOG_LEVEL` | todos os serviços | `INFO` | Debug de incidente sem redeploy. |

#### Runtime do transpilador (7 — não aplicáveis ao compose)

Executam em dev/CI quando o desenvolvedor roda `uv run python -m transpiler`. Não entram no `.env.example` do compose; documentados em `docs/CONFIGURATION.md § Variáveis do transpiler`.

| # | Variável | Arquivo fonte | Default | Justificativa |
|---|---|---|---|---|
| T1 | `TRANSPILER_SPEC_MAX_BYTES` | `transpiler/transpiler/schema.py` | `1048576` (1 MB) | Specs maiores em projetos complexos (mais mcp_servers, mais http_tools). |
| T2 | `TRANSPILER_MAX_URL_LEN` | `transpiler/transpiler/schema.py` | `2048` | URLs com query strings longas. |
| T3 | `TRANSPILER_MAX_INSTRUCTION_BYTES` | `transpiler/transpiler/schema.py` | `4096` | Prompt maior em modelos com janela de contexto maior. |
| T4 | `TRANSPILER_MAX_MCP_SERVERS` | `transpiler/transpiler/schema.py` | `10` | Agente com mais tools MCP. |
| T5 | `TRANSPILER_MAX_HTTP_TOOLS` | `transpiler/transpiler/schema.py` | `20` | Idem para HTTP tools. |
| T6 | `TRANSPILER_MAX_TOOL_FILTER` | `transpiler/transpiler/schema.py` | `50` | Idem para `tool_filter` por servidor. |
| T7 | `TRANSPILER_AGENT_PY_MAX_BYTES` | `transpiler/transpiler/generator.py` | `102400` (100 KB) | Spec grande pode legitimamente gerar `agent.py` maior. |

Defaults T1–T7 coincidem com os caps ADR-0008 — esta ADR torna-os tunáveis sem alterar o contrato ADR-0008 quando o operador/avaliador opera dentro do envelope.

### Tabela 2 — HARDCODED (17 parâmetros)

Permanecem literais no código. Cada item tem razão específica para **não** ser exposto. O guard `tests/infra/test_adr_0009_surface.py` protege o subconjunto crítico (H1–H6 calibrações Presidio, H8–H10 contrato público, H14 `SERVICE`, H16 linguagens suportadas). Os demais itens (H11–H13 host/ports, H15 `lru_cache`, H17 timeout de fixture) permanecem tutelados apenas pela revisão desta ADR — mudar qualquer um quebraria compose/healthcheck no próprio E2E antes de chegar ao guard, o que foi considerado suficiente.

#### Calibrações Presidio internas (7)

Scores por recognizer e o `score_threshold=0.5` interno em `analyzer.analyze()` formam um **sistema acoplado**. Mudar um isoladamente quebra a semântica em modo silencioso (ex.: CPF inválido em contexto tem score 0.45, abaixo do threshold global — isso é design; expor `_SCORE_INVALID` por env abre uma armadilha de configuração em que o operador desliga a validação de dígito sem saber).

| # | Constante | Arquivo | Valor | Justificativa |
|---|---|---|---|---|
| H1 | `_SCORE_VALID` (CPF) | `security/security/guard.py` (CPF recognizer) | `0.85` | Calibrado contra `PII_SCORE_THRESHOLD`. |
| H2 | `_SCORE_INVALID` (CPF) | idem | `0.1` | Idem — define FP intencional. |
| H3 | `_SCORE_VALID` (CNPJ) | CNPJ recognizer | `0.85` | Idem. |
| H4 | `_SCORE_INVALID` (CNPJ) | CNPJ recognizer | `0.1` | Idem. |
| H5 | `_SCORE_BASE` (phone) | Phone recognizer | `0.75` | Idem. |
| H6 | `_SCORE_BASE` (RG) | RG recognizer | `0.5` | Idem. |
| H7 | `score_threshold` interno em `analyzer.analyze()` | `security/security/guard.py` | `0.5` | Já é representado externamente por `PII_SCORE_THRESHOLD`; o literal interno é o contrato de calibração. |

#### Contrato público de API (3)

Campos `max_length` do Pydantic schema da `scheduling-api`. Mudar é **breaking change** do contrato consumido pelo agente e documentado em `/docs` (Swagger) — exige nova versão de API, não env var.

| # | Campo | Arquivo | Valor | Justificativa |
|---|---|---|---|---|
| H8 | `patient_ref` `max_length` | `scheduling_api/scheduling_api/models.py` | `64` | Contrato público do schema. |
| H9 | `exams[]` `max_length` | `scheduling_api/scheduling_api/models.py` | `20` | Contrato público. |
| H10 | `notes` `max_length` | `scheduling_api/scheduling_api/models.py` | `500` | Contrato público. |

#### Infraestrutura interna de container (4)

Valores acoplados a três lugares (Dockerfile, `docker-compose.yml`, URLs clientes). Expor como env sem coordenar os três é garantia de drift.

| # | Valor | Arquivo | Valor | Justificativa |
|---|---|---|---|---|
| H11 | `host="0.0.0.0"` (OCR MCP) | `ocr_mcp/ocr_mcp/server.py` | `0.0.0.0` | Bind para aceitar conexões do compose network; mudar quebra comunicação. |
| H12 | `host="0.0.0.0"` (RAG MCP) | `rag_mcp/rag_mcp/server.py` | `0.0.0.0` | Idem. |
| H13 | `port=8001` / `port=8002` / `port=8000` | servers + Dockerfiles + compose | — | Contrato triplo com `docker-compose.yml` e URLs dos clientes; sem ganho operacional real. |
| H14 | `SERVICE="scheduling-api"` (e equivalentes) em logging | cada módulo | string literal | Identificador de serviço nos logs estruturados; fonte da verdade por serviço. |

#### Algorítmicos internos (3)

| # | Valor | Arquivo | Valor | Justificativa |
|---|---|---|---|---|
| H15 | `@lru_cache(maxsize=2)` / `maxsize=1` (engine Presidio) | `security/security/engine.py` | `2` / `1` | Otimização interna; impacto operacional mínimo. |
| H16 | `_SUPPORTED_LANGUAGES = {"pt", "en"}` | `security/security/engine.py` | `{"pt", "en"}` | Adicionar idioma exige baixar spaCy model + bake no Dockerfile + testes; não é mudança de env. |
| H17 | `timeout=60.0` em E2E fixtures | `tests/e2e/conftest.py` | `60.0` | Fixture de teste, não runtime. |

### Padrão de leitura e coordenação com Docker

- **Leitura em Python**: `os.environ.get("VAR", "default-literal")`. Nenhuma lib de config adicional (pydantic-settings, dynaconf) — a superfície não justifica a dependência.
- **Propagação no compose**: `docker-compose.yml` expõe cada variável por serviço com sintaxe `${VAR:-default}`. O default no compose **deve espelhar** o default no código; divergência é bug.
- **spaCy models**: `PII_SPACY_MODEL_PT` é **simultaneamente** env var e build-arg. Os Dockerfiles (`ocr_mcp/Dockerfile`, `generated_agent/Dockerfile`, `transpiler/transpiler/templates/Dockerfile.j2`) recebem `ARG PII_SPACY_MODEL_PT=pt_core_news_lg` e executam `RUN python -m spacy download $PII_SPACY_MODEL_PT` para baixar o modelo **durante o build**. Alterar o modelo exige `docker compose build` para re-bake; mudar só o `.env` não basta. Essa coordenação está documentada em `docs/CONFIGURATION.md § Modelos spaCy e coordenação Dockerfile`.
- **Model Literal ampliado**: `AgentSpec.model` passa de `Literal["gemini-2.5-flash"]` para `Literal["gemini-2.5-flash", "gemini-2.5-flash-lite"]`. Novo modelo aceitos pela validação do spec; o runtime continua honrando o override via `GEMINI_MODEL`.

### Supersessão parcial de ADR-0006

ADR-0006 permanece vigente em todo o restante (schema do `AgentSpec`, topologia `LlmAgent` único, regra de "novo campo exige ADR nova"). O único ponto superseded é a lista aceita do campo `model` — ampliada para incluir `gemini-2.5-flash-lite` por esta ADR. O índice `docs/adr/README.md` registra a anotação *"parcialmente superseded por ADR-0009 no escopo do campo `model`"*.

## Consequências

**Positivas**:

- **Resposta operacional imediata ao incidente 503**: trocar `GEMINI_MODEL=gemini-2.5-flash-lite` (ou `gemini-flash-latest`) no `.env` e rodar `docker compose up -d --force-recreate generated-agent` reabilita o fluxo sem tocar em código.
- **Superfície documentada e auditável**: 26 vars descritas em `.env.example` com comentário de 1–2 linhas cada; visão do operador consolidada em `docs/CONFIGURATION.md`.
- **Disciplina preservada**: calibrações Presidio internas e contratos públicos da API continuam protegidos; guard de testes (`tests/infra/test_adr_0009_surface.py`) rejeita PRs que tentem env-ificar itens da Tabela 2.
- **Compatibilidade com ADR-0008**: todos os caps e timeouts da ADR-0008 continuam válidos como defaults; esta ADR apenas os torna tunáveis dentro do envelope operacional.

**Negativas / débito técnico**:

- Aumento da superfície de documentação: `.env.example` cresce de 8 para 26 linhas úteis; `CONFIGURATION.md` é novo; `code-reviewer` precisa validar coerência defaults código ↔ template ↔ compose ↔ `.env.example` ↔ ADR.
- ADR-0006 agora carrega anotação de supersessão parcial — operador que lê apenas a ADR-0006 precisa olhar também o índice para descobrir que o `Literal` foi ampliado.
- Adicionar um novo modelo Gemini à lista aceita exige PR atualizando esta ADR + o `Literal` + as mensagens de erro do schema. É fricção proposital: mudança de modelo é decisão consciente, não acidental.

**Impacto em outros subsistemas**:

- Template `transpiler/transpiler/templates/agent.py.j2` passa a emitir `model=os.environ.get("GEMINI_MODEL", {{ model | tojson }})` na linha do `LlmAgent` — o default do `.env.example` coincide com o valor do spec.
- `docs/ARCHITECTURE.md § Variáveis de ambiente` passa a remeter para `docs/CONFIGURATION.md` em vez de listar as vars diretamente (evita duplicação com drift).
- `ai-context/STATUS.md` recebe entrada para o bloco "env-config / ADR-0009".
- Runbook `docs/runbooks/e2e-manual-gemini.md` permanece o mesmo; a única mudança operacional é a possibilidade de editar `.env` em caso de 503 sem regenerar artefatos.

## Referências

- `docs/DESAFIO.md` — exigência de conteinerização via Docker Compose.
- `docs/adr/0001-mcp-transport-sse.md` — URLs MCP que agora são env-backed.
- `docs/adr/0003-pii-double-layer.md` — camada PII cujas constantes tunáveis viram env; calibrações por recognizer permanecem hardcoded.
- `docs/adr/0006-spec-schema-and-agent-topology.md` — **parcialmente superseded** no escopo do campo `model`.
- `docs/adr/0008-robust-validation-policy.md` — caps e timeouts cujos defaults foram preservados e agora são tunáveis.
- `docs/CONFIGURATION.md` — guia do operador com tabelas por serviço, playbooks de troca e coordenação Dockerfile.
- `.env.example` — superfície documentada do runtime do compose.
- Plano interno `eager-orbiting-pearl` — inventário completo dos 43 valores varridos e decomposição em ondas.
