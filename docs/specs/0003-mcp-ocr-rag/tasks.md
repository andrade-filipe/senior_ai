---
id: 0003-mcp-ocr-rag
status: todo
---

## Setup

- [ ] T001 [P] — Criar `ocr_mcp/pyproject.toml` com `mcp[cli]^1`, `pydantic^2.6`, `pytest^8`, dep local/stub para `security`. Adicionar `Pillow>=10` como **test dependency** (não runtime) para geração da fixture PNG em T002.
- [ ] T002 — Gerar `tests/fixtures/sample_medical_order.png` via Pillow — imagem com cabeçalho "Pedido Médico" + 3 a 5 nomes de exames do catálogo RAG + nome fake + CPF fake. Hash do arquivo é fixo (arquivo PNG é commitado no repositório — **não** gerado em runtime). O mock do OCR (`ocr_mcp/fixtures.py`) mapeia esse hash para o texto canônico correspondente, garantindo determinismo para o E2E (Bloco 8).
- [ ] T003 [P] — Criar `rag_mcp/pyproject.toml` com `mcp[cli]^1`, `rapidfuzz^3`, `pydantic^2.6`, `pytest^8`.
- [ ] T004 [P] — Criar estrutura `ocr_mcp/` com `__main__.py`, `server.py`, `fixtures.py`, `logging_.py` (placeholders).
- [ ] T005 [P] — Criar estrutura `rag_mcp/` com `__main__.py`, `server.py`, `catalog.py`, `data/exams.csv` (header só), `logging_.py` (placeholders).
- [ ] T006 — **Dependência externa**: garantir que o Bloco 5 T001 já entregou o stub identity oficial em `security/__init__.py` (assinatura `pii_mask(text, language="pt", allow_list=None) -> MaskedResult(masked_text=text, entities=[])`). Se o Bloco 5 T001 ainda não estiver em GREEN, o engenheiro do Bloco 3 **não cria stub local** — pede desbloqueio no checkpoint #1.
- [ ] T007 [P] — Criar `tests/ocr_mcp/conftest.py` e `tests/rag_mcp/conftest.py` com fixture `tmp_catalog_csv` (5 linhas) e `fake_image_base64`.

## Tests (same-commit — RED opcional)

Tests seguem padrão same-commit (ADR-0004) — engenheiro pode escrever teste e código juntos. Listados aqui para rastreabilidade contra ACs.

- [ ] T010 [P] — Teste para [AC1] em `tests/ocr_mcp/test_server_integration.py::test_sse_handshake_exposes_tool` (subprocess FastMCP + cliente MCP SSE).
- [ ] T011 [P] — Teste para [AC2] em `tests/ocr_mcp/test_fixtures.py::test_known_hash_returns_canned_list` (determinismo R11).
- [ ] T012 [P] — Teste para [AC3] em `tests/ocr_mcp/test_fixtures.py::test_unknown_hash_returns_empty_without_error`.
- [ ] T013 [P] [DbC] — Teste para [AC4] em `tests/ocr_mcp/test_pii_guard.py::test_output_has_no_raw_pii` (fixture contém `CPF 111.444.777-35`) — DbC: `extract_exams_from_image.Post` (PII linha 1).
- [ ] T014 [P] — Teste para [AC5] em `tests/rag_mcp/test_server_integration.py::test_sse_handshake_exposes_two_tools`.
- [ ] T015 [P] [DbC] — Teste para [AC6] em `tests/rag_mcp/test_catalog.py::test_csv_has_100_plus_entries` (usa CSV real, não fixture) — DbC: `catalog.load.Post` (≥ 100 elementos).
- [ ] T016 [P] [DbC] — Teste para [AC7] em `tests/rag_mcp/test_catalog.py::test_exact_match_returns_high_score` — DbC: `search_exam_code.Post`.
- [ ] T017 [P] [DbC] — Teste para [AC8] em `tests/rag_mcp/test_catalog.py::test_typo_below_threshold_returns_none` — DbC: `search_exam_code.Post` (threshold 80/100).
- [ ] T018 [P] — Teste para [AC9] em `tests/rag_mcp/test_catalog.py::test_alias_match_resolves_to_canonical_code`.
- [ ] T019 [P] — Teste para [AC10] em `tests/rag_mcp/test_catalog.py::test_list_exams_limit_5_ordered`.
- [ ] T020 [P] — Teste para [AC11] em `tests/ocr_mcp/test_logging.py::test_tool_called_event_emitted` + análogo em `tests/rag_mcp/`.
- [ ] T021 [P] — Teste para [AC12] em `tests/ocr_mcp/test_healthcheck.py::test_head_sse_returns_200_or_405` + análogo em RAG.
- [ ] T024 [P] [DbC] — Teste para [AC13] em `tests/rag_mcp/test_catalog.py::test_exam_match_score_in_0_1_range` (property-check: para matches positivos, `0.0 <= ExamMatch.score <= 1.0`; para no-match, retorno é `None`, nunca score fora do intervalo) — DbC: `search_exam_code.Invariant` (`score ∈ [0,1]`).
- [ ] T025 [P] [DbC] — Teste para [AC14] em `tests/rag_mcp/test_catalog.py::test_duplicate_code_rejected_with_line_ref` (CSV com código duplicado → `CatalogError` citando linha e valor: ex.: `duplicate code 'B2' at line 47`) — DbC: `catalog.load.Invariant` (code único).
- [ ] T026 [P] [DbC] — Teste para [AC18] em `tests/rag_mcp/test_catalog.py::test_rag_query_too_large_rejected` (query de 501 chars → `ToolError(code="E_RAG_QUERY_TOO_LARGE")`; `rapidfuzz` nunca chamado — mock assert) — DbC: `search_exam_code.Pre` (query size).
- [ ] T027 [P] [DbC] — Teste para [AC19] em `tests/rag_mcp/test_catalog.py::test_rag_empty_query_rejected` (`""`, `"   "` → `ToolError(code="E_RAG_QUERY_EMPTY")`) — DbC: `search_exam_code.Pre` (non-empty).
- [ ] T028 [P] — Teste para [AC20] em `tests/rag_mcp/test_server_startup.py::test_catalog_load_failure_shape` (arquivo inexistente OU header inválido → stderr contém JSON com `code=E_CATALOG_LOAD_FAILED`, `message`, `hint`, `path`, `context`; exit ≠ 0).
- [ ] T029 [P] [DbC] — Teste para [AC21] em `tests/rag_mcp/test_catalog.py::test_rag_search_timeout` (monkey-patch `rapidfuzz.process.extractOne` com sleep > 2s → `ToolError(code="E_RAG_TIMEOUT")`) — DbC: `search_exam_code.Post` (timeout).
- [ ] T030 [P] [DbC] — Teste para [AC20] complemento em `tests/rag_mcp/test_catalog.py::test_catalog_load_missing_file_error` (`path` inexistente → `CatalogError(code="E_CATALOG_LOAD_FAILED")` com `context.path` ref) — DbC: `catalog.load.Post`.
- [ ] T031 [P] [DbC] — Teste para [AC15] em `tests/ocr_mcp/test_guards.py::test_image_too_large_rejected` (base64 de 6 MB decodificado → `ToolError(code="E_OCR_IMAGE_TOO_LARGE")`; `sha256` nunca chamado) — DbC: `extract_exams_from_image.Pre` (image size).
- [ ] T032 [P] [DbC] — Teste para [AC16] em `tests/ocr_mcp/test_guards.py::test_invalid_base64_rejected` (string `"não é base64!"`, `""` → `ToolError(code="E_OCR_INVALID_INPUT")`) — DbC: `extract_exams_from_image.Pre` (base64 válido).
- [ ] T033 [P] [DbC] — Teste para [AC17] em `tests/ocr_mcp/test_guards.py::test_ocr_timeout` (monkey-patch do lookup com sleep > 5s → `ToolError(code="E_OCR_TIMEOUT")`) — DbC: `extract_exams_from_image.Post` (timeout).

## Implementation (same-commit GREEN)

- [ ] T030 — Implementar `ocr_mcp/logging_.py` (JSON logger) — helper reaproveitável depois.
- [ ] T031 — Implementar `ocr_mcp/fixtures.py` com dict `FIXTURES: dict[str, list[str]]` cobrindo a fixture `sample_medical_order.png` (hash resolvido no Bloco 6).
- [ ] T032 — Implementar `ocr_mcp/server.py` com tool `extract_exams_from_image` chamando `fixtures.lookup(image_base64)` e passando resultado por `security.pii_mask` antes de retornar (ADR-0003).
- [ ] T033 — Implementar `ocr_mcp/__main__.py` com `mcp.run(transport="sse", host="0.0.0.0", port=8001)` (ADR-0001).
- [ ] T034 [P] — Implementar `rag_mcp/logging_.py` (idem T030 — pode duplicar agora; Bloco 8 unifica se preciso).
- [ ] T035 [P] — Implementar `rag_mcp/catalog.py::load(path)` com leitura CSV + validação de colunas + unique `code` (AC6).
- [ ] T036 — Implementar tools `search_exam_code` e `list_exams` em `rag_mcp/server.py` usando `rapidfuzz.process.extractOne` com threshold 80 (ADR-0007) (AC7, AC8, AC9, AC10).
- [ ] T037 — Implementar `rag_mcp/__main__.py` com `mcp.run(transport="sse", host="0.0.0.0", port=8002)`.
- [ ] T038 — Popular `rag_mcp/data/exams.csv` com ≥ 100 linhas de exames (hematologia, bioquímica, hormônios, urinálise, imagem simples) com colunas `name,code,category,aliases` (AC6). Derivado de SIGTAP (fonte primária) com fallback TUSS — ver ADR-0007 § "Fonte do dataset". Granulado em T038.1..T038.5:
  - [ ] T038.1 — Baixar SIGTAP (ou clonar `rdsilva/SIGTAP`). **Registrar URL + data de acesso em `ai-context/LINKS.md` no mesmo commit** (sem rastreabilidade → sem merge, GUIDELINES § 6).
  - [ ] T038.2 [P] — Extrair colunas brutas (`codigo_sus, descricao, forma_organizacional, grupo`) do SIGTAP e converter para CSV intermediário em `rag_mcp/data/_sigtap_raw.csv` (gitignored).
  - [ ] T038.3 [P] — Filtrar por categorias de laboratório + imagem simples → ≥ 120 linhas. Salvar em `rag_mcp/data/_filtered.csv` (gitignored).
  - [ ] T038.4 [P] — Transformar para schema ADR-0007 (`name,code,category,aliases`); inferir aliases a partir de variações de nomenclatura (siglas, abreviações). Saída final: `rag_mcp/data/exams.csv`.
  - [ ] T038.5 — Validar: rodar `test_csv_has_100_plus_entries` (T015) + confirmar zero `code` duplicado + confirmar ausência de PII (nenhum paciente, nenhum dado pessoal — só nomenclatura e códigos).
- [ ] T039 — Implementar `Dockerfile` em cada pacote (`ocr_mcp/Dockerfile`, `rag_mcp/Dockerfile`) seguindo template do Bloco 7 plan.

## Refactor

- [ ] T040 — Extrair função `normalize_exam_name(s)` reutilizada em RAG (strip, lowercase, unicodedata NFKD) se aparecer duplicada.
- [ ] T041 — Revisar docstrings Google-style nas duas tools MCP (GUIDELINES § 1).
- [ ] T042 — Rodar `uv run ruff check .` + `uv run mypy ocr_mcp/ rag_mcp/` (non-strict) e zero warnings.

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0003-mcp-ocr-rag.md`: `uv run pytest tests/ocr_mcp/ tests/rag_mcp/`, exemplo de log JSON emitido, `wc -l rag_mcp/data/exams.csv` mostrando ≥ 100.
- [ ] T091 — Anexar output do cliente MCP ao chamar `extract_exams_from_image` com a fixture canônica (AC2).

## Paralelismo

Setup `[P]` (T001, T003–T005, T007) e tests `[P]` (T010–T021) rodam em paralelo. T002 (fixture PNG) é sequencial após T001 (precisa de `Pillow` instalado) mas independente do resto. T006 é um check de dependência externa (Bloco 5 T001) — não produz código local. T030–T033 (OCR) e T034–T038 (RAG) podem ser feitos em paralelo por duas pessoas/sessions distintas; T039 depende de T033+T037 para saber o CMD. Quando o Bloco 5 troca o stub identity pelo `pii_mask` real (T038 do Bloco 5), o teste de PII-leak (T013) deste bloco passa a exercitar a implementação definitiva — sem necessidade de mudar imports aqui.
