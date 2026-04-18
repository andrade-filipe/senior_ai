---
id: 0003-mcp-ocr-rag
status: proposed
---

## Abordagem técnica

Dois processos FastMCP independentes, cada um em seu pacote Python com `pyproject.toml` próprio (ADR-0005). Transporte SSE obrigatório (ADR-0001). Observabilidade via logs JSON estruturados ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Formato de log"). Guardrails de input, timeouts e shape canônico de erro conforme [ADR-0008](../../adr/0008-robust-validation-policy.md).

```
ocr_mcp/
├── __main__.py         # inicia o server (mcp.run(transport="sse", ...))
├── server.py           # tool registrations + lifecycle
├── fixtures.py         # dict hash(imagem) -> texto canned (R11)
├── logging_.py         # JSON formatter (cópia leve; Bloco 8 consolida)
└── pyproject.toml

rag_mcp/
├── __main__.py
├── server.py
├── catalog.py          # carrega CSV, indexa por name+aliases
├── data/
│   └── exams.csv       # ≥ 100 linhas (ADR-0007)
├── logging_.py
└── pyproject.toml
```

### OCR MCP

- `extract_exams_from_image(image_base64: str) -> list[str]` (assinatura congelada em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Assinaturas exatas das tools MCP").
- Mock determinístico: `sha256(base64_decode(image_base64))` → lookup em `fixtures.py`; fallback para lista vazia.
- **Linha 1 do PII guard** (ADR-0003): antes de retornar, junta os exames em `"; ".join(names)`, passa por `security.pii_mask`, parse de volta para `list[str]`. Alternativa mais simples: aplicar `pii_mask` item a item (menos CPU, mais chamadas) — escolha final fica em RED com o engenheiro.

### RAG MCP

- `catalog.load(path: Path) -> list[ExamEntry]` — carrega CSV UTF-8 (`csv.DictReader`), valida colunas `name,code,category,aliases` na ordem.
- Tabela de choices para `rapidfuzz.process.extractOne` inclui `name` e cada alias, mapeando de volta ao `code` canônico.
- `search_exam_code(exam_name: str) -> ExamMatch | None` com threshold fixo 80 (ADR-0007); retorna `ExamMatch(name=canonical, code, score=raw/100)`.
- `list_exams(limit: int = 100) -> list[ExamSummary]` — slice do catálogo na ordem do CSV.

### Catálogo CSV

Formato congelado em ADR-0007. **Fonte primária**: SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos do SUS — DATASUS, domínio público), filtrado para ≥ 120 exames laboratoriais e de imagem comuns (hematologia, bioquímica, hormônios, urinálise, imagem simples). **Fallback**: TUSS (ANS, ODS público em `dados.gov.br`). O engenheiro escolhe entre baixar `.txt` oficial DATASUS ou usar conversão CSV comunitária MIT (`rdsilva/SIGTAP`); em qualquer caso registra URL + data de acesso em `ai-context/LINKS.md` no mesmo commit.

**Restrição absoluta** (PII-zero): nenhum dado de paciente — apenas nomenclatura e códigos. LOINC e CBHPM foram explicitamente rejeitados em ADR-0007 § "Fonte do dataset" por fricção de licença.

Derivação do CSV final (colunas `name,code,category,aliases`) fica granularizada em `T038.1..T038.5` de `tasks.md`.

### Observabilidade

Cada MCP expõe um `JsonLogger` local que emite linhas com `{ts, level, service, event, correlation_id, message, extra}`. `correlation_id` vem do metadata do MCP quando disponível; caso contrário gerado localmente como `mcp-<uuid4>[:8]`.

## Data models

```python
# rag_mcp/catalog.py
class ExamEntry(BaseModel):
    name: str
    code: str
    category: str
    aliases: list[str]   # sep: "|" no CSV

class ExamMatch(BaseModel):    # ARCHITECTURE § "rag-mcp"
    name: str
    code: str
    score: float  # 0..1

class ExamSummary(BaseModel):
    name: str
    code: str
```

```python
# ocr_mcp/fixtures.py
FIXTURES: dict[str, list[str]] = {
    "sha256-do-sample-medical-order": ["Hemograma Completo", "Glicemia de Jejum", "Colesterol Total"],
    # ...
}
```

**Fixture PNG**: `tests/fixtures/sample_medical_order.png` é gerado via **Pillow** no setup (T002) e **commitado** no repositório — não é gerado em runtime. Isso garante determinismo: o `sha256` do arquivo é estável entre ambientes e serve como chave única no dict `FIXTURES`. O conteúdo visual inclui cabeçalho "Pedido Médico" + 3 a 5 exames do catálogo RAG + nome fake + CPF fake (para exercitar PII no pipeline).

## Contratos

Forma-completa descrita em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Contratos entre subsistemas" e § "Assinaturas exatas das tools MCP". **Não reescrever aqui.**

Fronteiras:
- `ocr-mcp:8001/sse` (SSE) — tool `extract_exams_from_image`.
- `rag-mcp:8002/sse` (SSE) — tools `search_exam_code`, `list_exams`.

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `search_exam_code(exam_name)` | `exam_name` é `str` ≤ 500 chars não-vazia após `strip()` (ADR-0008); timeout 2 s | retorna `ExamMatch` com `score ∈ [0,1]` **ou** `None` quando abaixo do threshold 80/100 | `score` nunca negativo nem > 1; `code` retornado existe no catálogo | AC7, AC8, AC13, AC18, AC19, AC21 | T016 `[DbC]`, T017 `[DbC]`, T024 `[DbC]`, T026 `[DbC]`, T027 `[DbC]`, T029 `[DbC]` |
| `catalog.load(path)` | `path` aponta para CSV UTF-8 com header `name,code,category,aliases` | retorna `list[ExamEntry]` com ≥ 100 elementos; em falha, serializa erro no shape canônico ADR-0008 | `code` é único em todo o catálogo; levanta se duplicado | AC6, AC14, AC20 | T015 `[DbC]`, T025 `[DbC]`, T030 `[DbC]` |
| `extract_exams_from_image(image_base64)` | input é base64 válido ≤ 5 MB decodificado (ADR-0008); timeout 5 s | saída já passou por `security.pii_mask` (ADR-0003, linha 1) | nenhum valor PII cru retornado — teste T013 enforça | AC4, AC15, AC16, AC17 | T013 `[DbC]`, T031 `[DbC]`, T032 `[DbC]`, T033 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `mcp[cli]` | `^1.0` | FastMCP + transporte SSE (ADR-0001) | Implementar SSE manualmente (rejeitado) |
| `rapidfuzz` | `^3` | Fuzzy match (ADR-0007) | `difflib` stdlib (rejeitado — lento para N≥100) |
| `pydantic` | `^2.6` | Modelos `ExamMatch`, `ExamEntry` | — |
| `pytest-asyncio` | `^0.23` | Testes do cliente MCP | — |
| `Pillow` | `>=10` | **Test-only**: geração da fixture `sample_medical_order.png` (T002) — não é dep runtime do `ocr-mcp` | — |

Consome `security` (Bloco 5) via import. Importa `from security import pii_mask` desde o dia zero; enquanto Bloco 5 não preencher a implementação real, o **stub identity** exposto pelo `security/__init__.py` (T001 do Bloco 5 — retorna `MaskedResult(masked_text=text, entities=[])`) é suficiente para o pipeline compilar. Os testes unitários do OCR mock não dependem da lógica PII real; o teste de PII-leak (T013, AC4) passa a exercitar o `pii_mask` real quando o Bloco 5 entrar em GREEN e o stub for substituído.

## Riscos

| Risco | Mitigação |
|---|---|
| FastMCP SSE pode fechar conexão em ociosidade → cliente ADK reconecta. | Aceitável no MVP (compose mantém serviço up); E2E valida que reconnection funciona. |
| Healthcheck HTTP em `/sse` pode ser frágil. | Usar `service_started` no compose (ADR-0001) para MCPs; `service_healthy` apenas para API. |
| Catálogo CSV pode ter typos (ex.: código duplicado). | Validação no `load()`: rejeitar duplicatas de `code`, reportar linha. |
| Import de `security` antes do Bloco 5 estar em GREEN quebra o RED do Bloco 3. | Stub identity oficial exposto pelo próprio Bloco 5 (T001): `security/__init__.py` entrega desde o dia zero um `pii_mask` passthrough (`MaskedResult(masked_text=text, entities=[])`). Assinatura é definitiva; implementação real entra em T038 do Bloco 5. Resolvido arquitetonicamente — sem stub temporário em `ocr_mcp/`. |
| Mocks de OCR podem divergir das fixtures usadas no Bloco 8 (E2E). | Fixture canônica (`sample_medical_order.png`) é commitada no Bloco 8 mas **hash é calculado e registrado neste bloco** para garantir determinismo. |

## Estratégia de validação

- **Same-commit** (GUIDELINES § 4, ADR-0004): testes e código juntos em `tests/ocr_mcp/`, `tests/rag_mcp/`.
- **Unit**: `catalog.load` contra CSV fixture pequeno (5 linhas); `search_exam_code` com casos de match exato, alias, typo, no-match; fixture de OCR testa lookup por hash.
- **Integration**: subir `ocr-mcp` em subprocesso + cliente MCP `mcp.client.sse` chamando a tool — valida SSE handshake (AC1, AC5). Idem para `rag-mcp`.
- **PII leak test**: rodar `extract_exams_from_image` com fixture contendo nome + CPF no texto canned, verificar que a saída não contém nenhum dos valores originais (AC4).
- **Catálogo ≥ 100**: teste `assert len(load(...)) >= 100` (AC6).
- **Cobertura**: não é gate (≥ 80 % só em `transpiler/` e `security/` por ADR-0004), mas apontado em evidência para inspeção.

**Estratégia de validação atualizada (ADR-0008)**:
- **OCR image size (AC15)**: `extract_exams_from_image` mede `len(base64.b64decode(image_base64, validate=True))` antes do `sha256`; > 5 MB → `ToolError(code="E_OCR_IMAGE_TOO_LARGE")` com bytes observados vs cap.
- **OCR invalid input (AC16)**: `base64.b64decode(..., validate=True)` em `try/except`; `binascii.Error` ou string vazia → `ToolError(code="E_OCR_INVALID_INPUT")`.
- **OCR timeout (AC17)**: envolver pipeline em `asyncio.wait_for(..., timeout=5.0)`; `asyncio.TimeoutError` → `ToolError(code="E_OCR_TIMEOUT")`.
- **RAG query size (AC18)**: guard no início de `search_exam_code` — `len(exam_name) > 500` → `ToolError(code="E_RAG_QUERY_TOO_LARGE")`.
- **RAG empty query (AC19)**: após `strip()`, string vazia → `ToolError(code="E_RAG_QUERY_EMPTY")` com hint em PT-BR.
- **Catalog load failure (AC20)**: `rag_mcp/__main__.py` envolve `catalog.load()` em `try/except CatalogError`; em falha, usa `format_challenge_error()` (helper do Bloco 1) para emitir linha canônica em stderr e `sys.exit(1)`.
- **RAG timeout (AC21)**: envolver `rapidfuzz.process.extractOne` em `asyncio.wait_for(..., timeout=2.0)`; timeout → `ToolError(code="E_RAG_TIMEOUT")`.

## Dependências entre blocos

- **Depende**, em código, do Bloco 5 (`security.pii_mask`) — mas no nível de **spec/contrato** já está em ADR-0003 e ARCHITECTURE, então o engenheiro pode iniciar RED em paralelo com o Bloco 5 (stub temporário).
- **Independente** de Blocos 1, 2, 4 no nível de spec.
- **Bloqueia** o Bloco 6 (agente precisa das tools para consumir) e o Bloco 7 (compose precisa dos Dockerfiles que cada engenheiro entrega consigo — ver ADR-0005).
