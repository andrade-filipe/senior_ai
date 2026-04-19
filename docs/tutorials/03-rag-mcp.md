# Tutorial 03 — Servidor MCP de RAG (`rag-mcp`)

## 1. Objetivo

Ao final deste tutorial você será capaz de:

- Subir o serviço `rag-mcp` de forma isolada dentro da rede Docker Compose.
- Entender as duas tools expostas (`search_exam_code` e `list_exams`) e o algoritmo de busca.
- Adicionar novos exames ao catálogo sem tocar no código.
- Diagnosticar falhas com os códigos `E_RAG_*` e `E_CATALOG_*`.

---

## 2. Pré-requisitos

| Item | Detalhe |
|---|---|
| Docker + Docker Compose v2.20+ | `docker compose version` deve retornar `>= 2.20`. |
| Imagem construída | `docker compose build rag-mcp`. |
| `.env` presente | Copie `.env.example` para `.env`. Para este serviço apenas `LOG_LEVEL` é relevante. Sem `GOOGLE_API_KEY` — o RAG MCP não chama LLM. |

O serviço **não publica porta ao host** (sem bloco `ports:` no `docker-compose.yml`). Para acesso direto a partir do host use `docker compose exec rag-mcp` ou um container auxiliar na mesma rede.

---

## 3. Como invocar

### 3.1 Subir apenas o serviço

```bash
docker compose up -d rag-mcp
```

O servidor fica em `http://rag-mcp:8002/sse` dentro da rede Compose. Confirme o carregamento do catálogo nos logs:

```bash
docker compose logs rag-mcp | grep catalog
```

Linha esperada:

```json
{"event": "catalog.loaded", "entry_count": 118, "choice_count": 412}
```

O campo `entry_count` reflete o número de linhas de dados no CSV. `choice_count` é maior porque inclui todas as aliases.

### 3.2 Verificar que o endpoint SSE responde

```bash
docker compose exec rag-mcp \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8002/sse', timeout=2).status)"
```

Saída esperada: `200`.

### 3.3 Chamar as tools via script Python dentro da rede

O padrão é o mesmo do `ocr-mcp` (Tutorial 02): `McpToolset` + `StreamableHTTPConnectionParams` (ADR-0001), apontando para `http://rag-mcp:8002/sse`. Substitua `tool_filter` por `["search_exam_code", "list_exams"]` e adapte os `args` conforme a seção 5.

---

## 4. Contratos resumidos

Os contratos públicos estão definidos em:

- [`docs/ARCHITECTURE.md` § "Assinaturas exatas das tools MCP"](../ARCHITECTURE.md#assinaturas-exatas-das-tools-mcp) — assinaturas `ExamMatch`, `ExamSummary` e as tools.
- [`docs/ARCHITECTURE.md` § "Catálogo de exames (CSV)"](../ARCHITECTURE.md#catalogo-de-exames-csv) — formato de colunas congelado.
- [ADR-0001](../adr/0001-mcp-transport-sse.md) — transporte SSE.
- [ADR-0007](../adr/0007-rag-fuzzy-and-catalog.md) — escolha de `rapidfuzz` + threshold 80 + estrutura do CSV.
- [`docs/specs/0003-mcp-ocr-rag/`](../specs/0003-mcp-ocr-rag/) — spec, plan e tasks do bloco.

Fontes do dataset: SIGTAP (primária — DATASUS, domínio público) e TUSS (ANS, fallback). Consulte `ai-context/LINKS.md` § "Catálogos de nomenclatura médica (BR)" para URLs e datas de acesso.

---

## 5. Exemplos completos

### 5.1 Busca com match acima do threshold

```python
# Chamada
search_exam_code(exam_name="Hemograma")

# Resposta (ExamMatch)
{"name": "Hemograma Completo", "code": "HMG-001", "score": 0.93}
```

O campo `score` está normalizado em `[0.0, 1.0]` (rapidfuzz retorna `0–100`; o servidor divide por 100). Threshold efetivo: `0.80`.

### 5.2 Busca via alias

O catálogo inclui aliases separados por `|` na coluna `aliases`. Exemplo de linha do CSV:

```
Hemograma Completo,HMG-001,hematologia,Hemograma|HMC|CBC|Hemograma Completo com Plaquetas
```

Buscar por `"HMC"` retorna o mesmo `ExamMatch` com `code=HMG-001`.

### 5.3 Sem match (score abaixo de 80)

```python
search_exam_code(exam_name="xkZqPTesInexistente")
# Retorno: null (None em Python)
```

Quando o retorno é `null`, o agente deve chamar `list_exams(limit=20)` e apresentar sugestões ao usuário (instrução congelada em `generated_agent/agent.py`).

### 5.4 Listagem paginada

```python
list_exams(limit=5)
# Retorno: [
#   {"name": "Hemograma Completo", "code": "HMG-001"},
#   {"name": "Glicemia de Jejum",  "code": "GLI-001"},
#   {"name": "Colesterol Total",   "code": "COL-001"},
#   {"name": "Colesterol HDL",     "code": "COL-002"},
#   {"name": "Colesterol LDL",     "code": "COL-003"}
# ]
```

### 5.5 Log de uma busca bem-sucedida

```json
{"ts": "2026-04-19T10:01:00.456Z", "level": "INFO", "service": "rag-mcp",
 "event": "tool.called",
 "extra": {"tool": "search_exam_code", "duration_ms": 1.2, "matched": true}}
```

---

## 6. Como adicionar um exame novo

Siga estes quatro passos na ordem:

**a) Edite o CSV mantendo as colunas obrigatórias.**

Abra `rag_mcp/rag_mcp/data/exams.csv` e adicione uma linha ao final. Exemplo:

```
Proteína C-Reativa,PCR-001,inflamacao,PCR|CRP|Proteina C Reativa Ultrassensivel
```

Requisitos: `code` deve ser único no arquivo; encoding UTF-8 sem BOM; sem linhas em branco no meio; separador `,` (não `;`).

**b) Reconstrua a imagem Docker.**

```bash
docker compose build rag-mcp
```

**c) Suba o serviço atualizado.**

```bash
docker compose up -d rag-mcp
```

**d) Verifique nos logs que `entry_count` subiu.**

```bash
docker compose logs rag-mcp | grep catalog.loaded
```

A linha deve mostrar `"entry_count": N` onde `N` é o total anterior + 1.

---

## 7. Troubleshooting

### E_RAG_QUERY_TOO_LARGE

**Quando ocorre:** `exam_name` tem mais de 500 caracteres.

```json
{"code": "E_RAG_QUERY_TOO_LARGE",
 "message": "`exam_name` excede 500 chars",
 "hint": "Envie apenas o nome do exame, sem contexto extra",
 "context": {"chars_received": 612, "chars_max": 500}}
```

Solução: truncar ou isolar apenas o nome do exame antes de chamar a tool.

### E_RAG_QUERY_EMPTY

**Quando ocorre:** `exam_name` é vazio ou contém apenas espaços.

```json
{"code": "E_RAG_QUERY_EMPTY",
 "message": "`exam_name` está vazia",
 "hint": "Envie o nome do exame"}
```

### E_RAG_TIMEOUT

**Quando ocorre:** a busca `rapidfuzz` excede 2 s. Improvável com catálogo de ~120 entradas, mas possível em ambiente com contenção de CPU severa.

```json
{"code": "E_RAG_TIMEOUT",
 "message": "RAG não respondeu em 2 s",
 "hint": "Verifique se `rag-mcp` está saudável"}
```

Solução: `docker compose ps rag-mcp`; reinicie se necessário.

### E_CATALOG_LOAD_FAILED — CSV malformado

**Quando ocorre:** na inicialização do servidor, se o CSV tiver encoding não-UTF-8, header inválido, código duplicado ou arquivo vazio.

```json
{"code": "E_CATALOG_LOAD_FAILED",
 "message": "Falha ao carregar catálogo: duplicate code 'HMG-001' at line 45 (first seen at line 2)",
 "hint": "Inspecione `rag_mcp/data/exams.csv`"}
```

O servidor **aborta a inicialização** nesse caso. Inspecione os logs de startup:

```bash
docker compose logs rag-mcp | head -30
```

### Sem matches acima do threshold para nomes válidos

O threshold padrão é 80 (escala rapidfuzz `0–100`). Se um nome correto retornar `null`, verifique:

1. Se existe alias correspondente no CSV (coluna `aliases`).
2. O nome enviado pode ter acentuação diferente. O `WRatio` do rapidfuzz tolera variações, mas diferenças ortográficas muito grandes (ex.: `"RX Torax"` vs `"Radiografia de Tórax"`) podem ficar abaixo de 80.

Solução: adicione o alias problemático na coluna `aliases` da entrada correspondente e reconstrua.

---

## 8. Onde estender

- **Spec e tasks:** [`docs/specs/0003-mcp-ocr-rag/`](../specs/0003-mcp-ocr-rag/)
- **Ajustar threshold:** constante `THRESHOLD = 80` em `rag_mcp/rag_mcp/catalog.py`. Mudança deve ser justificada — threshold menor aumenta falsos positivos.
- **Trocar scorer rapidfuzz:** função `search()` em `rag_mcp/rag_mcp/catalog.py` usa `fuzz.WRatio`. Substituir por `fuzz.token_sort_ratio` ou embeddings exige ADR nova supersedendo ADR-0007.
- **Expandir catálogo:** seguir o processo da seção 6. O dataset inicial é derivado de SIGTAP (ver ADR-0007 § "Fonte do dataset").
