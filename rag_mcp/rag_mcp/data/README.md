# rag_mcp/data

Catalog data for the RAG MCP server.

## exams.csv

Medical exam catalog, UTF-8, comma-separated.

**Columns** (in this exact order, per ADR-0007):
- `name` — canonical exam name (e.g. `Hemograma Completo`)
- `code` — unique canonical code (e.g. `HMG-001`)
- `category` — clinical group (e.g. `hematologia`)
- `aliases` — alternative names separated by `|` (e.g. `Hemograma|HMC|CBC`)

**Invariants**:
- Header must be on line 1 exactly as `name,code,category,aliases`
- `code` must be unique across all rows
- No patient data — only exam nomenclature and codes

**Source**: Derived from SIGTAP (DATASUS), domain public (LAI), accessed 2026-04-19.
See `ai-context/LINKS.md` § "Catálogos de nomenclatura médica (BR)" for full source citations.
