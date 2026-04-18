# ADR-0007: RAG MCP via rapidfuzz + catálogo CSV

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

O desafio exige um servidor MCP "RAG" que, dado o nome de um exame extraído pelo OCR, devolva o código canônico do exame a partir de um catálogo com **≥ 100 exames**. "RAG" aqui é usado em sentido amplo — busca sobre conhecimento estruturado, não necessariamente vetorial.

Nomes de exames vêm do OCR com ruído: variações de caixa (`HEMOGRAMA` vs `Hemograma`), abreviações (`Hb` vs `Hemoglobina`), typos, acentuação ausente. Precisamos de um mecanismo de busca que tolere essas variações sem custo de infra alto.

## Alternativas consideradas

1. **rapidfuzz (escolhido)** — fuzzy string matching em C otimizado; `rapidfuzz.process.extractOne(name, catalog)` retorna match e score em microssegundos.
   - Prós: zero cold-start, zero dependência pesada, tolera variações ortográficas, score objetivo.
   - Contras: não captura sinônimos semânticos (`glicemia` ↔ `glicose`); mitigado com coluna `aliases` no CSV.

2. **Embeddings locais (sentence-transformers)** — vetoriza cada nome e busca por similaridade de cossenos.
   - Prós: captura sinônimos.
   - Contras: dependência ~500 MB (modelo); cold-start de segundos; overkill para catálogo pequeno.

3. **Exact match com normalização** (`str.lower()`, `strip`, `unicodedata.normalize("NFKD")`).
   - Prós: zero deps, trivial.
   - Contras: falha em variações mínimas; muito frágil.

## Decisão

### Busca

- Lib: `rapidfuzz`.
- Função principal: `rapidfuzz.process.extractOne(query, choices, scorer=fuzz.WRatio)`.
- **Threshold inicial: 80** (escala 0–100). Abaixo disso, a tool retorna `None`.
- Fallback: quando `search_exam_code` retorna `None`, o agente pode chamar `list_exams(limit=100)` e apresentar sugestões top-N.
- Nomes na `choices` incluem os campos `name` **e** cada `alias`; o mapping preserva o `code` canônico.

### Catálogo

- Formato: **CSV** em `rag_mcp/data/exams.csv`, UTF-8, separador `,`.
- Colunas (nessa ordem):
  - `name` — nome canônico (ex.: `Hemograma Completo`).
  - `code` — código do exame (ex.: `HMG-001`).
  - `category` — grupo clínico (ex.: `hematologia`).
  - `aliases` — outros nomes separados por `|` (ex.: `Hemograma|HMG|HMC`).
- Header obrigatório. Comentários via linha iniciando com `#` não são aceitos — use o `README` do diretório.
- Carregamento: no startup do servidor, em memória (`list[ExamEntry]`), indexado por `code`.

### Contratos das tools MCP

```python
class ExamMatch(BaseModel):
    name: str
    code: str
    score: float   # 0..1 (rapidfuzz /100)

class ExamSummary(BaseModel):
    name: str
    code: str

@mcp.tool()
def search_exam_code(exam_name: str) -> ExamMatch | None: ...
@mcp.tool()
def list_exams(limit: int = 100) -> list[ExamSummary]: ...
```

### Dataset inicial

Conteúdo do CSV (≥ 100 entradas) é produzido no bloco de implementação do RAG MCP (não nesta fase). Estrutura fica congelada aqui.

### Fonte do dataset

Derivado de **SIGTAP** (Sistema de Gerenciamento da Tabela de Procedimentos do SUS — DATASUS, domínio público), filtrado para ≥ 120 exames laboratoriais e de imagem comuns. Fallback: **TUSS** (ANS, ODS público em `dados.gov.br`). O engenheiro do Bloco 3 escolhe entre baixar `.txt` oficial DATASUS ou usar conversão CSV comunitária MIT (`rdsilva/SIGTAP`); em qualquer caso registra URL + data em `ai-context/LINKS.md`. **Restrição absoluta**: nenhum dado de paciente — apenas nomenclatura e códigos. LOINC e CBHPM foram descartados (licença friction / redistribuição restrita).

## Consequências

- **Positivas**: latência sub-milissegundo; dataset versionado e diff-friendly; avaliador pode inspecionar/editar o CSV; sem dependências pesadas em produção.
- **Negativas**: variações semânticas profundas falham; mitigável adicionando aliases no CSV. Se virar dor recorrente, abrimos ADR para embeddings.
- **Impacto**: `adk-mcp-engineer` implementa o loader e as tools; `qa-engineer` cria fixture CSV enxuto para unit tests + CSV real ≥ 100 entradas para integration/E2E; threshold ajustado no futuro via ADR.

## Referências

- https://github.com/rapidfuzz/RapidFuzz
- https://maxbachmann.github.io/RapidFuzz/
- `docs/ARCHITECTURE.md` — seção "Assinaturas exatas das tools MCP"
- `ai-context/references/MCP_SSE.md`
- `ai-context/LINKS.md` § "Catálogos de nomenclatura médica (BR)" — SIGTAP, TUSS, LOINC (rejeitado).

> Editado em 2026-04-18 durante fase pré-implementação: adicionada subseção "Fonte do dataset" fixando SIGTAP (primária) + TUSS (fallback) como origens públicas sem PII; LOINC/CBHPM registrados como descartados por licença. Sem mudança de mérito arquitetural — refinamento operacional permitido inline conforme `ai-context/references/DESIGN_AUDIT.md`.
