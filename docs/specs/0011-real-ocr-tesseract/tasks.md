---
id: 0011-real-ocr-tesseract
status: in_progress
---

## Setup

- [ ] T001 — abrir `docs/EVIDENCE/0011-real-ocr-tesseract.md` com header, contexto do incidente de 2026-04-20 e seções placeholder (Runbook, Output, Hashes, Evidência Docker).

## Tests (TDD RED)

Testes devem **falhar** antes das tasks de Implementation começarem. Escritos por `qa-engineer`. Todos os testes vivem em `ocr_mcp/tests/unit/` exceto onde indicado.

- [ ] T010 [P] [DbC] — `tests/unit/test_ocr.py::test_extract_returns_lines_from_synthesized_image` — PIL sintetiza imagem 400x100 branca com `ImageDraw.text((10,30), "Hemograma Completo", fill="black", font=ImageFont.load_default())`; `await ocr.extract_exam_lines(bytes, lang="por", timeout_s=5.0)` retorna lista contendo substring "Hemograma" (tolerância a OCR imperfeito — startswith ou `in`). Cobre AC2.
- [ ] T011 [P] [DbC] — `tests/unit/test_ocr.py::test_extract_returns_empty_when_image_is_noise` — imagem branca sem texto → retorno `[]`. Cobre AC4.
- [ ] T012 [P] [DbC] — `tests/unit/test_fixtures.py::test_lookup_returns_none_on_miss_and_copy_on_hit` — dois casos: (a) base64 de bytes aleatórios → `lookup(...) is None`; (b) base64 da fixture canônica (após `_ensure_fixture_registered`) → lista igual a `_SAMPLE_EXAMS`; mutar o retorno não afeta `FIXTURES[hash]`. Cobre AC1, AC10.
- [ ] T013 [P] [DbC] — `tests/unit/test_server.py::test_do_ocr_uses_fixture_fast_path` — `monkeypatch.setattr(fixtures, "lookup", lambda b64: ["Canned"])`; `monkeypatch.setattr(ocr, "extract_exam_lines", AsyncMock())`; invocar `_do_ocr(b64)`; assert `ocr.extract_exam_lines.assert_not_awaited()`. Cobre AC1.
- [ ] T014 [P] [DbC] — `tests/unit/test_server.py::test_do_ocr_falls_back_to_real_ocr_on_miss` — `fixtures.lookup` → `None`; `ocr.extract_exam_lines` → `AsyncMock(return_value=["Hemograma"])`; invocar `_do_ocr(b64_of_random_bytes)`; assert `extract_exam_lines` awaited once com bytes decodificados iguais ao base64 input. Cobre AC2.
- [ ] T015 [P] [DbC] — `tests/unit/test_ocr.py::test_filter_heuristics` — helper interno `_filter_lines(raw_text: str) -> list[str]` (ou teste pelo comportamento pub de `extract_exam_lines` com mock de `pytesseract.image_to_string`): input "Paciente: João\nHemograma Completo\n  \nCPF: 111\nEcg" → saída `["Hemograma Completo", "Ecg"]` (header drop, whitespace drop, min-len respeitado — "Ecg" tem 3 chars, passa). Cobre AC2, AC4 (filtro).
- [ ] T016 [P] [DbC] — `tests/unit/test_server.py::test_do_ocr_pii_masks_real_ocr_output` — `ocr.extract_exam_lines` retorna `["Paciente João Silva CPF 111.444.777-35 Hemograma"]` (pass-through cru); `_do_ocr` retorna lista cujo único item **não contém** "111.444.777-35" nem "João Silva" (mascarados pela Layer 1). Cobre AC3.
- [ ] T017 [P] [DbC] — `tests/unit/test_server.py::test_extract_tool_timeout_when_real_ocr_hangs` — `monkeypatch` `ocr.extract_exam_lines` para `asyncio.sleep(10)`; env `OCR_TIMEOUT_SECONDS=0.2`; chamar `extract_exams_from_image(b64)` → `ToolError` com código `E_OCR_TIMEOUT`. Cobre AC6.

## Implementation (TDD GREEN)

Código mínimo para passar T010..T017. Pode paralelizar entre arquivos distintos.

- [ ] T020 — `ocr_mcp/ocr_mcp/ocr.py` (NOVO): implementar `extract_exam_lines(image_bytes, *, lang="por", timeout_s=5.0) -> list[str]` com `pytesseract.image_to_string` em `asyncio.to_thread` + filtro (header blacklist, min/max len, cap 64) + `assert` de invariantes de saída. Antes de escrever, rodar `grep -r "fixtures.lookup\|from.*fixtures.*import.*lookup" ocr_mcp/` para confirmar callers de `fixtures.lookup`.
- [ ] T021 [P] — `ocr_mcp/ocr_mcp/fixtures.py`: refactor `lookup()` para retornar `list[str] | None`; docstring atualizada. **Bloqueia** T022.
- [ ] T022 — `ocr_mcp/ocr_mcp/server.py::_do_ocr`: substituir `names = lookup(image_base64)` por `names = fixtures.lookup(b64); if names is None: names = await ocr.extract_exam_lines(decoded, lang=_TESSERACT_LANG, timeout_s=_OCR_TIMEOUT_S)`. Ler `_TESSERACT_LANG` de `os.environ.get("OCR_TESSERACT_LANG", "por")` no topo do módulo.
- [ ] T023 [P] — `ocr_mcp/pyproject.toml`: adicionar `pytesseract>=0.3.10,<1` e `Pillow>=10.0.0,<12` em `[project] dependencies`. Remover `Pillow>=10` de `[dependency-groups].dev` se passou a ser runtime (manter se QA tests separados ainda usam).
- [ ] T024 [P] — `ocr_mcp/Dockerfile`: adicionar bloco `RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por && rm -rf /var/lib/apt/lists/*` imediatamente após `FROM python:3.12-slim` e antes do `pip install uv`. Verificar imagem builda localmente.
- [ ] T025 [P] — `.env.example` (raiz): adicionar `OCR_TESSERACT_LANG=por` com comentário citando ADR-0009 e spec 0011. `docker-compose.yml` service `ocr-mcp`: passar `OCR_TESSERACT_LANG=${OCR_TESSERACT_LANG:-por}` em `environment:`.
- [ ] T026 — `ocr_mcp/ocr_mcp/__init__.py` (se existir) ou no topo do módulo: garantir que `ocr` é importável; `from ocr_mcp import ocr` funciona.

## Refactor (TDD REFACTOR)

Só após T010..T017 verdes.

- [ ] T030 — se `_filter_lines` surgir como helper privado duplicado entre `ocr.py` e testes, extrair como função pública `ocr._filter_lines` (com leading underscore apenas) e testar diretamente. Sem mudança de comportamento.
- [ ] T031 — se `server._do_ocr` ganhar complexidade acima de McCabe 8, extrair `_resolve_exam_names(b64)` (fast-path ou real) como função privada no server. Só se aplicável.

## Integration

- [ ] T040 [P] — `ocr_mcp/tests/integration/test_tesseract_available.py::test_binary_on_path_and_por_installed` — `@pytest.mark.integration`. Asserta `shutil.which("tesseract")` + `"por" in subprocess.check_output(["tesseract", "--list-langs"]).decode()`. Skipa se binário ausente.
- [ ] T041 [P] — `ocr_mcp/tests/integration/test_real_fixture_ocr.py::test_extract_from_canonical_fixture_png` — lê `ocr_mcp/tests/fixtures/sample_medical_order.png`; chama `await ocr.extract_exam_lines(bytes, lang="por", timeout_s=10.0)`; asserta pelo menos 1 linha retornada com `len >= 3`. Tolerante a imperfeições — o fast-path cobre a forma canônica; este teste prova que **Tesseract funciona de verdade**.

## E2E (fora do escopo desta spec mas referenciado)

- [ ] T080 — `tests/e2e/test_e2e_real_ocr.py::test_canonical_fixture_end_to_end` — reutiliza infra do bloco 0008; roda o docker compose; asserta exit 0 + tabela ASCII + `appointment_id`. Em ambiente sem docker (CI sem docker-in-docker), `@pytest.mark.e2e` + skip.

## Evidence

- [ ] T090 — rodar `uv run pytest ocr_mcp/ -v --cov=ocr_mcp` e anexar saída (pass count + cov ≥ 85% para `ocr.py`) em `docs/EVIDENCE/0011-real-ocr-tesseract.md § Unit + Integration`.
- [ ] T091 — rodar `docker build -t ocr-mcp:0011 ./ocr_mcp` + `docker run --rm ocr-mcp:0011 which tesseract` + `docker run --rm ocr-mcp:0011 tesseract --list-langs | grep por` e anexar logs em § Build.
- [ ] T092 — rodar `docker compose up -d` + `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` e anexar stdout completo (tabela ASCII + `appointment_id`) em § E2E.
- [ ] T093 — rodar o mesmo E2E com uma **imagem arbitrária** (não a fixture do repo — gerada por `PIL` no runbook da evidência) para provar que o OCR real funciona sem o fast-path. Anexar em § E2E-arbitrary.
- [ ] T094 — flip de status: `spec.md` → `implemented`, `plan.md` → `done`, `tasks.md` → `done`, `ai-context/STATUS.md` bloco 11 → `done`. ADR-0011 → `accepted`.

## Paralelismo

- **RED**: T010, T011, T012, T013, T014, T015, T016, T017 são todos `[P]` — arquivos de teste distintos (ou testes distintos em mesmo arquivo sem fixtures conflitantes).
- **GREEN**: T020 (`ocr.py`) é serial (novo arquivo, sem dependência). T021 bloqueia T022 (server depende do novo contrato). T023, T024, T025 são `[P]` entre si e com T020 (arquivos distintos: `pyproject.toml`, `Dockerfile`, `.env.example`/`docker-compose.yml`).
- **INTEGRATION**: T040 e T041 `[P]` (arquivos distintos, ambos `@pytest.mark.integration`).
- **EVIDENCE**: T090..T093 sequenciais (E2E depende de build; arbitrary E2E depende de compose up).

## Owners sugeridos

- RED (T010..T017): `qa-engineer`.
- GREEN code (T020..T022, T026): `adk-mcp-engineer`.
- GREEN infra (T023..T025): `devops-engineer`.
- Refactor (T030, T031): autor do GREEN.
- Integration (T040, T041): `qa-engineer`.
- Evidence (T090..T094): `qa-engineer` + `software-architect`.
