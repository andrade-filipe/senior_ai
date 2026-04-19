# Evidências — Bloco 0003: Servidores MCP OCR e RAG

**Status**: Em progresso — aguardando execução de `uv run pytest` pelo orquestrador.

## Checklist de Evidências

### T090 — pytest

```
# Executar:
cd ocr_mcp && uv sync && uv run pytest -v
cd rag_mcp && uv sync && uv run pytest -v
```

Resultado esperado: 0 falhas, cobertura ≥ 80%.

### T090 — wc -l rag_mcp/data/exams.csv

```
wc -l rag_mcp/data/exams.csv
```

Resultado esperado: ≥ 101 (header + 100 linhas de dados).

### T090 — Exemplo de log JSON emitido

```json
{
  "ts": "2026-04-19T12:00:00.123Z",
  "level": "INFO",
  "service": "ocr-mcp",
  "event": "tool.called",
  "message": "extract_exams_from_image ok",
  "extra": {
    "tool": "extract_exams_from_image",
    "duration_ms": 3.2,
    "exam_count": 5
  }
}
```

### T091 — Chamada ao ocr-mcp com fixture canônica

```python
# Cliente Python exemplo (após subir o servidor):
import asyncio, base64
from mcp import ClientSession
from mcp.client.sse import sse_client

async def call_ocr():
    with open("ocr_mcp/tests/fixtures/sample_medical_order.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    async with sse_client("http://localhost:8001/sse") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool("extract_exams_from_image", {"image_base64": b64})
            print(result)

asyncio.run(call_ocr())
# Expected output: ["Hemograma Completo", "Glicemia de Jejum", "Colesterol Total", "TSH", "Creatinina"]
```

## Arquivos criados/modificados

### `ocr_mcp/`
- `pyproject.toml` — deps: mcp[cli], pydantic, security (local editable)
- `ocr_mcp/__init__.py`
- `ocr_mcp/__main__.py` — entrada `python -m ocr_mcp`, porta 8001
- `ocr_mcp/server.py` — tool `extract_exams_from_image`, guards AC15/AC16/AC17
- `ocr_mcp/fixtures.py` — mock determinístico SHA256 → lista de exames
- `ocr_mcp/errors.py` — `OcrError(ChallengeError)`
- `ocr_mcp/logging_.py` — JSON logger
- `Dockerfile`
- `tests/conftest.py` — fixtures pytest, gera sample_medical_order.png
- `tests/test_fixtures.py` — T011, T012 (AC2, AC3)
- `tests/test_guards.py` — T031, T032, T033 (AC15, AC16, AC17)
- `tests/test_pii_guard.py` — T013 (AC4, DbC PII)
- `tests/test_logging.py` — T020 (AC11)
- `tests/test_healthcheck.py` — T021 (AC12)
- `tests/generate_fixture.py` — helper script

### `rag_mcp/`
- `pyproject.toml` — deps: mcp[cli], rapidfuzz, pydantic
- `rag_mcp/__init__.py`
- `rag_mcp/__main__.py` — entrada `python -m rag_mcp`, porta 8002
- `rag_mcp/server.py` — tools `search_exam_code` + `list_exams`, guards AC18/AC19/AC21
- `rag_mcp/catalog.py` — `load()`, `build_choices()`, `search()`
- `rag_mcp/models.py` — `ExamEntry`, `ExamMatch`, `ExamSummary`
- `rag_mcp/errors.py` — `CatalogError`, `RagError` (herdando `ChallengeError`)
- `rag_mcp/logging_.py` — JSON logger
- `rag_mcp/data/exams.csv` — 115 exames SIGTAP-derivados (>= 100)
- `Dockerfile`
- `tests/conftest.py` — fixtures pytest
- `tests/test_catalog.py` — T015–T019, T024–T030
- `tests/test_logging.py` — T020 (AC11)
- `tests/test_healthcheck.py` — T014, T021 (AC5, AC12)
- `tests/test_server_startup.py` — T028 (AC20)

## Notas de implementação

- **Timeout OCR (AC17)**: `asyncio.wait_for(..., timeout=5.0)` — suficiente para mock puro Python (sem I/O bloqueante). `multiprocessing.Pool` seria overkill para lookup em dict.
- **Timeout RAG (AC21)**: `asyncio.wait_for(..., timeout=2.0)` — mesmo raciocínio; rapidfuzz é C puro, coopera com asyncio.
- **PII (AC4)**: `pii_mask()` aplicado item a item — mais simples que join/split; overhead negligível para listas de 3-5 nomes.
- **Catálogo**: derivado de SIGTAP (ver `ai-context/LINKS.md`); 115 exames em 9 categorias.
