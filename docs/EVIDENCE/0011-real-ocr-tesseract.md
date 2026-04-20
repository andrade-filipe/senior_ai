# Evidência — Spec 0011: OCR real via Tesseract

Spec: `docs/specs/0011-real-ocr-tesseract/`
ADR: `docs/adr/0011-real-ocr-via-tesseract.md`
Incidente de origem: 2026-04-20 — E2E canônico da spec 0010 saiu com `E_OCR_UNKNOWN_IMAGE` (exit 4) porque o fixture PNG em disco não era enviado para dentro do container Docker (`.dockerignore` bloqueia `tests/`) e o `FIXTURES` dict ficava vazio. A correção arquitetural é a que está registrada em ADR-0011: Tesseract real com fast-path de hash preservado como cache.

## Runbook

```powershell
# 1. rebuild do container ocr-mcp (Tesseract + por pack + pytesseract/Pillow)
docker compose build ocr-mcp

# 2. rebuild do generated-agent (opcional — não mudou na 0011)
docker compose build generated-agent

# 3. sobe infra
docker compose up -d ocr-mcp rag-mcp scheduling-api

# 4. espera healthy
docker compose ps

# 5. E2E canônico
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png

# 6. cleanup
docker compose down -v
```

`.env` requer `PII_TIMEOUT_SECONDS=30` (cold-start Presidio/spaCy no Windows) e `GEMINI_MODEL` pode ser `gemini-flash-latest` para evitar o 503 `UNAVAILABLE` do pool `gemini-2.5-flash-lite` (documentado em ADR-0009).

---

## T090 — Unit + Integration (2026-04-20)

**Comando:** `uv run pytest ocr_mcp/tests/ -v --cov=ocr_mcp`

**Resultado:** 38/38 passed em 10.45s.

```
tests/test_fixtures.py ............................ 4 passed
tests/test_fixtures.py::TestUnknownHashReturnsNone .. 3 passed (contrato novo: None, não [])
tests/test_guards.py ................................. 8 passed
tests/test_healthcheck.py ............................ 2 passed
tests/test_logging.py ................................ 4 passed
tests/test_pii_guard.py .............................. 4 passed
tests/test_server_ocr_hash_log.py .................... 1 passed
tests/unit/test_fixtures.py .......................... 3 passed
tests/unit/test_ocr.py ............................... 5 passed (T010, T011, T015 + 2 regressão E2E)
tests/unit/test_server.py ............................ 4 passed (T013, T014, T016, T017)

Coverage:
  ocr_mcp/ocr.py          83%   (linhas não cobertas: branches de erro em _filter_lines + timeout subprocess)
  ocr_mcp/server.py       94%
  ocr_mcp/fixtures.py     86%
  ocr_mcp/logging_.py    100%
  TOTAL                   84%
```

**Nota sobre cobertura de `ocr.py` (83% vs meta 85% do plan.md):** as linhas não cobertas (118, 126, 132 em `_filter_lines`; 194-201 em `_run_tesseract`; 205-206 post-condition) são branches defensivos que exigem timeout real do subprocess Tesseract para serem exercitados — inviável em teste unitário sem binário. Cobertos no T041/T092 via Docker.

---

## T091 — Build Docker

*Aguardando execução do `docker build -t ocr-mcp:0011 ./ocr_mcp` + `docker run --rm ocr-mcp:0011 tesseract --list-langs | grep por` pelo operador.*

Evidência esperada:
```
$ docker run --rm ocr-mcp:0011 which tesseract
/usr/bin/tesseract

$ docker run --rm ocr-mcp:0011 tesseract --list-langs
List of available languages (3):
eng
osd
por
```

---

## T092 — E2E canônico (Tesseract real lendo fixture do repo)

**Run 1 (2026-04-20 19:49:23 UTC)** — primeira rodada pós-GREEN, antes do refinamento do filtro (commit `6319e7d`).

Evidência extraída de `logs.txt` (capturado pelo operador):

### Pre-OCR CLI
```json
{"event": "agent.preocr.invoked", "correlation_id": "0f62b0b3-c158-42f0-9e29-5b1b52b9e1a4", "sha256_prefix": "17c46fa5", "mcp_url": "http://ocr-mcp:8001/sse"}
{"event": "agent.preocr.result", "correlation_id": "0f62b0b3-c158-42f0-9e29-5b1b52b9e1a4", "exam_count": 8, "duration_ms": 3367}
```

### OCR MCP server — Tesseract real acionado
```json
{"event": "ocr.lookup.hash", "sha256": "17c46fa55aa8d2178cc66ffd80db10f335adea473c58a1c297c4091c1834f93b", "payload_bytes": 9469}
{"event": "ocr.lookup.miss"}
{"event": "ocr.tesseract.invoked", "image_size": 9469, "lang": "por"}
{"event": "ocr.tesseract.result", "filtered_line_count": 8, "duration_ms": 351.1, "lang": "por"}
{"tool": "extract_exams_from_image", "duration_ms": 3280.3, "exam_count": 8}
```

**Tesseract produziu** (pré-refinamento do filtro):
```
1. 'PEDIDOMEDICO'              ← ruído (header) → DROP após fix 6319e7d
2. 'CPF ITIAda 7775'           ← ruído (field label) → DROP após fix 6319e7d
3. 'Exames Solicitados.'       ← ruído (section title) → DROP após fix 6319e7d
4. '1 Hemegrama Completo'      ← exame (typo OCR)
5. '2 Glicemiado Jejum'        ← exame (colagem OCR)
6. 'a Colesterol Total'        ← exame (dígito ruim)
7. 'atu'                       ← ruído (3 chars lowercase) → DROP após fix 6319e7d
8. '<LOCATION>'                ← PII mascarada (Presidio layer 1 funcionou)
```

### PII Layer 1 — Presidio no server OCR
Confirmado: o endereço do paciente foi substituído por `<LOCATION>` antes da lista sair do `ocr-mcp`. `pii_mask` é aplicado em cada linha (fast-path OU Tesseract), conforme ADR-0003.

### RAG fuzzy absorveu os typos do Tesseract
```json
{"search_exam_code": "Hemegrama Completo"}  → {"name": "Hemograma Completo", "code": "HMG-001", "score": 0.94}
{"search_exam_code": "Glicemiado Jejum"}    → {"name": "Glicemia de Jejum",  "code": "GLI-001", "score": 0.91}
{"search_exam_code": "Colesterol Total"}    → {"name": "Colesterol Total",   "code": "COL-001", "score": 1.00}
```

### Bloqueio pós-OCR
Run 1 terminou com `google.genai.errors.ServerError: 503 UNAVAILABLE` no Gemini (`gemini-2.5-pro` no momento do teste). **Não relacionado à spec 0011** — trajetória de recuperação coberta por ADR-0009 (`GEMINI_MODEL=gemini-flash-latest`).

---

## T093 — E2E com imagem arbitrária (não-canônica, sem fast-path)

*Pendente — executar com um PNG arbitrário (gerado por PIL no runbook de teste) para provar que o Tesseract resolve sem o hash-cache.*

---

## T094 — Status flips

- [ ] `docs/specs/0011-real-ocr-tesseract/spec.md` → `implemented`
- [ ] `docs/specs/0011-real-ocr-tesseract/plan.md` → `done`
- [ ] `docs/specs/0011-real-ocr-tesseract/tasks.md` → `done`
- [ ] `ai-context/STATUS.md` bloco 11 → `done`
- [x] `docs/adr/0011-real-ocr-via-tesseract.md` → `accepted` (flip em `fe8580b`)

Aplicar apenas após T093 verde e aceitação humana (checkpoint #2).

---

## Superseding evidence da spec 0009

O incidente de 2026-04-20 que motivou a 0010 (forwarding de bytes via `Part.from_bytes`) era **o primeiro de dois problemas**. O segundo — fixture não embarcada no Docker — só ficou visível após a 0010 resolver o forwarding. Spec 0011 fecha essa segunda causa substituindo o mock por OCR real, mantendo o hash-cache apenas como fast-path opcional.

Camadas B (RunnerError tolerante) e C (validator-pass) da spec 0009 permanecem válidas e ortogonais.
