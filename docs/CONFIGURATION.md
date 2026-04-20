# Guia de configuração

Este documento é a **referência do operador** para a superfície de configuração do sistema. Todas as variáveis documentadas aqui são parte do contrato operacional estabelecido em [ADR-0009](adr/0009-runtime-config-via-env.md).

## 1. Visão geral

O princípio que rege a configuração é simples:

> **O spec define o default; o `.env` sobrescreve em runtime para todo parâmetro com legitimidade operacional. Contratos arquiteturais e calibrações algorítmicas internas permanecem hardcoded.**

Na prática:

- **Spec (`spec.json`)** — declara o agente de forma versionada: nome, descrição, modelo Gemini aceito, instrução, servidores MCP, HTTP tools e guardrails. O transpilador emite `generated_agent/` a partir dele.
- **`.env`** — sobrescreve em runtime qualquer parâmetro operacional (modelo, timeouts, limites, thresholds, caminho de catálogo, modelos spaCy, nível de log). Não exige rebuild de imagem Docker na maior parte dos casos.
- **Código** — mantém hardcoded apenas contratos públicos (schema Pydantic da API), calibrações Presidio por-recognizer (acopladas ao threshold global) e infraestrutura interna do container (portas, host bind). Ver [ADR-0009 § Tabela 2](adr/0009-runtime-config-via-env.md#tabela-2--hardcoded-17-parâmetros).

O arquivo `.env.example` na raiz do repositório documenta a superfície inteira do runtime do compose com comentário por linha. Copie para `.env` e ajuste:

```bash
cp .env.example .env
# edite .env com os valores do seu ambiente (ao menos GOOGLE_API_KEY)
```

## 2. Variáveis por serviço

### 2.1 `generated-agent` (runtime do agente ADK)

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `GOOGLE_API_KEY` | *(sem default)* | Chave da Gemini API. **Obrigatória**; obter em <https://aistudio.google.com/app/apikey>. | `generated_agent/agent.py` |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | Alterna entre Gemini direct API e Vertex AI. Só mude se estiver hospedado no GCP com Vertex habilitado. | `generated_agent/agent.py` |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Modelo Gemini consumido pelo agente. Valores aceitos pelo schema do transpilador: `gemini-2.5-flash`, `gemini-2.5-flash-lite`. Mais detalhes em § 3. | `generated_agent/agent.py` |
| `AGENT_TIMEOUT_SECONDS` | `300` | Timeout total da execução do agente (wall-clock, em segundos). | `generated_agent/__main__.py` |
| `SCHEDULING_OPENAPI_FETCH_TIMEOUT_SECONDS` | `10` | Timeout HTTP do agente quando baixa o `openapi.json` da `scheduling-api` no boot. | `generated_agent/agent.py` |
| `PREOCR_MCP_TIMEOUT_SECONDS` | `10` | Timeout wall-clock do pré-OCR orquestrado pelo CLI (connect + `initialize` + `call_tool`). Na estourada: aborta com `E_OCR_UNKNOWN_IMAGE` (exit 4). ADR-0010 / spec 0010. | `generated_agent/preocr.py` |
| `PREOCR_MCP_CONNECT_RETRIES` | `1` | Número de retries em erros de transporte do pré-OCR antes de abortar com `E_MCP_UNAVAILABLE` (exit 5). Não reinicia em timeout. ADR-0010. | `generated_agent/preocr.py` |
| `OCR_MCP_URL` | `http://ocr-mcp:8001/sse` | URL SSE do OCR MCP. Use sempre o DNS do compose — `localhost` não funciona dentro do container. Também consumido pela etapa de pré-OCR da CLI. | `generated_agent/agent.py` |
| `RAG_MCP_URL` | `http://rag-mcp:8002/sse` | URL SSE do RAG MCP. Idem. | `generated_agent/agent.py` |
| `SCHEDULING_OPENAPI_URL` | `http://scheduling-api:8000/openapi.json` | URL do OpenAPI consumido pelo OpenAPIToolset do ADK. | `generated_agent/agent.py` |
| `LOG_LEVEL` | `INFO` | Nível de log Python (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). | todos |

### 2.2 `ocr-mcp`

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `OCR_IMAGE_MAX_BYTES` | `5242880` (5 MB) | Tamanho máximo da imagem decodificada (base64 → bytes). Acima disso: `E_OCR_IMAGE_TOO_LARGE`. | `ocr_mcp/ocr_mcp/server.py` |
| `OCR_TIMEOUT_SECONDS` | `5` | Timeout wall-clock para uma chamada do `extract_exams_from_image`. | `ocr_mcp/ocr_mcp/server.py` |
| `OCR_DEFAULT_LANGUAGE` | `pt` | Idioma passado para o `pii_mask` (Presidio) ao mascarar os resultados do OCR — **não** afeta o Tesseract (spec 0011 separou os dois). | `ocr_mcp/ocr_mcp/server.py` |
| `OCR_TESSERACT_LANG` | `por` | Código de idioma passado para o `pytesseract.image_to_string`. Requer que o pacote `tesseract-ocr-<lang>` esteja instalado no Dockerfile (o padrão `por` já é embarcado). | `ocr_mcp/ocr_mcp/server.py` (spec 0011 / ADR-0011) |
| `PII_*` (ver § 2.5) | — | Camada 1 do PII roda in-process dentro do `ocr-mcp`. | — |

### 2.3 `rag-mcp`

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `RAG_QUERY_MAX_CHARS` | `500` | Tamanho máximo da query `exam_name`. Acima disso: `E_RAG_QUERY_TOO_LARGE`. | `rag_mcp/rag_mcp/server.py` |
| `RAG_SEARCH_TIMEOUT_SECONDS` | `2` | Timeout wall-clock do `search_exam_code` / `list_exams`. | `rag_mcp/rag_mcp/server.py` |
| `RAG_FUZZY_THRESHOLD` | `80` | Score mínimo rapidfuzz (0–100) para considerar um match válido. Mais detalhes em § 5. | `rag_mcp/rag_mcp/catalog.py` |
| `RAG_CATALOG_PATH` | `/app/rag_mcp/rag_mcp/data/exams.csv` | Caminho absoluto do CSV dentro do container (o pacote é `COPY rag_mcp /app/rag_mcp`, e o CSV fica em `<pkg>/data/`). Para trocar por catálogo custom, ver § 4. | `rag_mcp/rag_mcp/server.py` |

### 2.4 `scheduling-api`

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `SCHEDULING_BODY_SIZE_LIMIT_BYTES` | `262144` (256 KB) | Tamanho máximo do body HTTP aceito pelo `BodySizeLimitMiddleware`. Acima disso: `E_API_PAYLOAD_TOO_LARGE`. | `scheduling_api/scheduling_api/app.py` |
| `SCHEDULING_REQUEST_TIMEOUT_SECONDS` | `10` | Timeout wall-clock de uma request. Acima disso: `E_API_TIMEOUT`. | `scheduling_api/scheduling_api/app.py` |

### 2.5 PII guard (compartilhado entre `ocr-mcp` e `generated-agent`)

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `PII_DEFAULT_LANGUAGE` | `pt` | Idioma default do Presidio quando o chamador não especifica. | `security/security/engine.py` |
| `PII_TEXT_MAX_BYTES` | `102400` (100 KB) | Tamanho máximo do texto aceito por `pii_mask()`. Acima disso: `E_PII_TEXT_SIZE`. | `security/security/guard.py` |
| `PII_CALLBACK_TEXT_MAX_BYTES` | `102400` (100 KB) | Mesmo limite aplicado pelo `before_model_callback` do ADK sobre prompt parts. | `security/security/callback.py` |
| `PII_ALLOW_LIST_MAX` | `1000` | Número máximo de itens na `allow_list`. Acima disso: `E_PII_ALLOW_LIST_SIZE`. | `security/security/guard.py` |
| `PII_TIMEOUT_SECONDS` | `5` | Timeout wall-clock (hard) de `pii_mask()`. Implementado via worker `multiprocessing` com `terminate()`. | `security/security/guard.py` |
| `PII_SCORE_THRESHOLD` | `0.5` | Score mínimo (0.0–1.0) para o Presidio mascarar uma entidade. Tuning clássico de FP/FN. Ver § 5. | `security/security/guard.py` |
| `PII_SPACY_MODEL_PT` | `pt_core_news_lg` | Modelo spaCy português baked na imagem. Trocar exige `docker compose build`. Ver § 6. | `security/security/engine.py` + Dockerfiles |
| `PII_SPACY_MODEL_EN` | `en_core_web_lg` | Modelo spaCy inglês baked na imagem. | `security/security/engine.py` + Dockerfiles |

## 3. Trocando o modelo Gemini

Este é o **caso de uso motivador da ADR-0009**. No E2E manual de 2026-04-20, o `gemini-2.5-flash` com function-calling retornou `HTTP 503 UNAVAILABLE` três vezes seguidas por saturação server-side do pool Google — enquanto `gemini-2.5-flash-lite`, `gemini-flash-latest` e `gemini-2.5-pro` respondiam normalmente no mesmo momento. Antes da ADR-0009 isso exigia editar código e regenerar; agora é uma linha no `.env`.

Passo a passo:

```bash
# 1. Editar .env
#    Trocar a linha:
#      GEMINI_MODEL=gemini-2.5-flash-lite
#    para o modelo desejado, por exemplo:
#      GEMINI_MODEL=gemini-2.5-flash
#      GEMINI_MODEL=gemini-flash-latest
#      GEMINI_MODEL=gemini-2.5-pro

# 2. Recriar apenas o container do agente (os MCPs e a API continuam de pé)
docker compose up -d --force-recreate generated-agent

# 3. Verificar que a nova variável foi propagada
docker compose exec generated-agent env | grep GEMINI_MODEL

# 4. Rodar o E2E e conferir que os logs não mencionam 503
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

Modelos aceitos pelo schema Pydantic do spec: `gemini-2.5-flash` e `gemini-2.5-flash-lite`. No **runtime**, o `GEMINI_MODEL` do `.env` sobrescreve o valor do spec sem validação contra o `Literal` — isso é intencional e permite usar `gemini-flash-latest`, `gemini-2.5-pro` ou qualquer modelo Gemini que o pool aceitar. Se o Google mudar o nome de um modelo ou deprecar o atual, o operador reage sem esperar deploy de código.

Adicionar um modelo à lista oficial de valores aceitos pelo spec exige PR atualizando a ADR-0009, o `Literal` em `transpiler/transpiler/schema.py` e as mensagens de erro do schema. É fricção proposital.

## 4. Trocando o catálogo RAG

O catálogo default é `rag_mcp/data/exams.csv` (115 exames SIGTAP). Para trocar por um CSV custom:

```bash
# Opção A — catálogo já está montado em outro caminho dentro do container
#   Edite .env:
#     RAG_CATALOG_PATH=/app/custom/meu-catalogo.csv
#   Recrie apenas o rag-mcp:
docker compose up -d --force-recreate rag-mcp

# Opção B — catálogo está no host e precisa ser montado
#   No docker-compose.yml, adicione ao serviço rag-mcp:
#     volumes:
#       - ./meu-catalogo.csv:/app/custom/meu-catalogo.csv:ro
#   Edite .env:
#     RAG_CATALOG_PATH=/app/custom/meu-catalogo.csv
#   Recrie:
docker compose up -d --force-recreate rag-mcp
```

O formato do CSV é congelado pela [ADR-0007](adr/0007-rag-fuzzy-and-catalog.md) — colunas `name,code,category,aliases` na primeira linha (header obrigatório), UTF-8, separador `,`, sem comentários `#`. `aliases` é lista separada por `|`.

Se o catálogo for significativamente maior, considere também aumentar `RAG_SEARCH_TIMEOUT_SECONDS` e `RAG_QUERY_MAX_CHARS` proporcionalmente.

## 5. Ajustando thresholds

Dois thresholds têm legitimidade operacional clara:

### 5.1 `RAG_FUZZY_THRESHOLD` (default `80`)

Score mínimo rapidfuzz — escala 0–100. Mais baixo = mais recall (pega mais candidatos, inclusive falsos positivos); mais alto = mais precisão (só aceita matches muito próximos, aumenta risco de `E_RAG_NO_MATCH`).

Recomendação:

- Catálogo pequeno e bem curado (< 200 entradas com aliases): `80`–`85`.
- Catálogo com muitos aliases próximos: `85`–`90`.
- Catálogo ruidoso ou queries com muito typo: `70`–`75`.

### 5.2 `PII_SCORE_THRESHOLD` (default `0.5`)

Score mínimo (0.0–1.0) para o Presidio mascarar uma entidade. Dial canônico de tuning FP/FN da biblioteca.

**Cuidado importante**: os scores dos recognizers brasileiros (CPF, CNPJ, telefone, RG) são **calibrados em conjunto** com este threshold e permanecem hardcoded — por exemplo, um CPF **inválido** (dígito verificador errado) em contexto dá score `0.45`, logo **não** é mascarado quando o threshold é `0.5`. Isso é design intencional (documentado em [ADR-0009 § Tabela 2](adr/0009-runtime-config-via-env.md#calibrações-presidio-internas-7)): a decisão de "CPF inválido em contexto não é PII" está codificada pela tupla (score por recognizer, threshold global).

Se você abaixar `PII_SCORE_THRESHOLD` para `0.4`, CPFs inválidos **passarão a ser mascarados** — pode ser o comportamento desejado em produção paranoica, mas não é o design padrão. Se você subir para `0.7`, alguns `PERSON` e `LOCATION` do Presidio stock vão deixar de ser mascarados.

Resumo:

- Baixar threshold (ex.: `0.3`): **mais mascaramento**, mais FP, menos FN. Paranoia defensiva.
- Subir threshold (ex.: `0.7`): **menos mascaramento**, mais FN, menos FP. Aceita vazamento em troca de menos ruído.

Não mexa nos scores por recognizer sem entender o acoplamento. Se precisar recalibrar um recognizer específico, abra PR atualizando ADR-0009 com o novo mapa e acompanhe dos testes de `security/`.

## 6. Modelos spaCy e coordenação Dockerfile

`PII_SPACY_MODEL_PT` e `PII_SPACY_MODEL_EN` são casos especiais: são **simultaneamente** env var (lidas em runtime por `security/security/engine.py`) e build-arg (usadas no Dockerfile para fazer o *bake* do modelo na imagem).

Os Dockerfiles (`ocr_mcp/Dockerfile`, `generated_agent/Dockerfile`, `transpiler/transpiler/templates/Dockerfile.j2`) têm:

```dockerfile
ARG PII_SPACY_MODEL_PT=pt_core_news_lg
RUN python -m spacy download $PII_SPACY_MODEL_PT
```

E o `docker-compose.yml` propaga o build-arg:

```yaml
generated-agent:
  build:
    context: .
    dockerfile: generated_agent/Dockerfile
    args:
      PII_SPACY_MODEL_PT: "${PII_SPACY_MODEL_PT:-pt_core_news_lg}"
```

**Consequência operacional**: trocar o modelo spaCy exige `docker compose build` para re-executar o bake. Mudar só o `.env` e fazer `up -d --force-recreate` **não basta** — o container subirá com o modelo antigo ainda cacheado na imagem e o `engine.py` tentará carregar um modelo que não foi baixado.

Playbook:

```bash
# Trocar para o modelo "small" (menos memória, qualidade inferior)
#   1. Editar .env:
#     PII_SPACY_MODEL_PT=pt_core_news_sm

#   2. Reconstruir as imagens afetadas
docker compose build ocr-mcp generated-agent

#   3. Subir novamente
docker compose up -d ocr-mcp generated-agent
```

Modelos alternativos usuais: `pt_core_news_sm` (pequeno), `pt_core_news_md` (médio), `pt_core_news_lg` (grande, default). Modelos transformer (`pt_core_news_trf`) também funcionam mas exigem muita RAM.

## 7. Variáveis do transpiler

Sete variáveis com prefixo `TRANSPILER_*` ajustam os caps do schema `AgentSpec`. Elas afetam **a execução do transpilador** (quando você roda `uv run python -m transpiler spec.json -o ./generated_agent`), **não o runtime do compose**. Por isso **não** estão no `.env.example` da raiz — ficam disponíveis no ambiente em que o transpilador é executado (dev local, CI, etc.).

| Variável | Default | Impacto | Arquivo fonte |
|---|---|---|---|
| `TRANSPILER_SPEC_MAX_BYTES` | `1048576` (1 MB) | Tamanho máximo do arquivo `spec.json`. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_MAX_URL_LEN` | `2048` | Tamanho máximo de qualquer URL em `mcp_servers`/`http_tools`. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_MAX_INSTRUCTION_BYTES` | `4096` | Tamanho máximo do campo `instruction`. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_MAX_MCP_SERVERS` | `10` | Itens máximos na lista `mcp_servers[]`. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_MAX_HTTP_TOOLS` | `20` | Itens máximos na lista `http_tools[]`. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_MAX_TOOL_FILTER` | `50` | Itens máximos em `tool_filter` de cada MCP server. | `transpiler/transpiler/schema.py` |
| `TRANSPILER_AGENT_PY_MAX_BYTES` | `102400` (100 KB) | Tamanho máximo do `agent.py` gerado. Acima disso: `E_TRANSPILER_RENDER_SIZE`. | `transpiler/transpiler/generator.py` |

Uso típico (spec grande):

```bash
TRANSPILER_MAX_MCP_SERVERS=20 \
TRANSPILER_MAX_HTTP_TOOLS=40 \
uv run python -m transpiler minha-spec-grande.json -o ./generated_agent
```

Os defaults coincidem com os caps normativos de [ADR-0008](adr/0008-robust-validation-policy.md) — alterar via env ajusta o comportamento sem mudar o contrato oficial.

## 8. Variáveis HARDCODED (não exponíveis)

Dezessete parâmetros permanecem literais no código por razões arquiteturais específicas. Resumo:

- **Calibrações Presidio por-recognizer** (CPF, CNPJ, telefone, RG): scores acoplados ao `PII_SCORE_THRESHOLD`; mudar isoladamente é mis-config trivial.
- **`max_length` do Pydantic da scheduling-api** (`patient_ref`, `exams[]`, `notes`): contrato público consumido pelo agente e exposto em `/docs` — mudar é breaking change.
- **Portas internas e host bind** dos containers: acoplamento triplo (Dockerfile `EXPOSE`, `docker-compose.yml`, URLs dos clientes) sem ganho operacional.
- **Identificadores de serviço em logs** (`SERVICE="scheduling-api"` etc.): fonte da verdade para observabilidade.
- **`lru_cache` sizes** no engine Presidio: otimização interna.
- **`_SUPPORTED_LANGUAGES = {"pt", "en"}`**: adicionar idioma exige baixar spaCy model + bake no Dockerfile + testes novos; não é mudança de env.
- **Timeouts de test fixtures**: não são runtime.

A lista completa com justificativa caso-a-caso está em [ADR-0009 § Tabela 2](adr/0009-runtime-config-via-env.md#tabela-2--hardcoded-17-parâmetros). Mudar qualquer item exige PR atualizando a ADR antes de tocar em código; o guard de testes `tests/infra/test_adr_0009_surface.py` rejeita PRs que tentem env-ificar um destes parâmetros sem passar pela ADR.
