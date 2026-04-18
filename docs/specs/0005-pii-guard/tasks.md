---
id: 0005-pii-guard
status: todo
---

## Setup

- [ ] T001 — Criar `security/pyproject.toml` com `presidio-analyzer^2.2`, `presidio-anonymizer^2.2`, `spacy^3.7`, `pycpfcnpj^1.8`, `pytest^8`, `pytest-cov^5`. Criar `security/__init__.py` expondo **stub identity** `pii_mask(text: str, language: str = "pt", allow_list: list[str] | None = None) -> MaskedResult` que retorna `MaskedResult(masked_text=text, entities=[])` — assinatura definitiva; implementação real entra em T038. O stub é suficiente para o Bloco 3 (OCR MCP) importar desde o dia zero, garantindo que o pipeline compile enquanto este bloco evolui em paralelo.
- [ ] T002 — Criar estrutura `security/` com `engine.py`, `models.py`, `errors.py`, `recognizers/{__init__.py,br_cpf.py,br_cnpj.py,br_rg.py,br_phone.py}` (placeholders). `__init__.py` já existe (T001).
- [ ] T003 — Configurar `mypy --strict` em `security/` no `pyproject.toml` (GUIDELINES § 1).
- [ ] T004 — Adicionar script no `pyproject.toml` / README do módulo para baixar `pt_core_news_lg`: `uv run python -m spacy download pt_core_news_lg` (documentar, não executar no CI ainda).
- [ ] T005 [P] — Criar `tests/security/conftest.py` com fixture `sample_text_pt` contendo nome, CPF válido, CPF inválido (dígito quebrado), telefone BR, e-mail, data clínica.

## Tests (TDD RED — obrigatório ADR-0004)

- [ ] T010 [P] [DbC] — Teste [AC1] em `tests/security/test_pii_mask.py::test_mask_replaces_person_and_cpf` — DbC: `pii_mask.Post` (masked_text não contém valor original).
- [ ] T011 [P] [DbC] — Teste [AC2] em `tests/security/test_pii_mask.py::test_entities_only_have_hash_not_raw` — DbC: `MaskedResult.entities.Invariant` (nunca carrega `value` cru).
- [ ] T012 [P] — Teste [AC3] em `tests/security/test_pii_mask.py::test_unsupported_language_raises_e_pii_language`.
- [ ] T013 [P] — Teste [AC4] em `tests/security/test_pii_mask.py::test_engine_failure_raises_e_pii_engine` (monkeypatch falhando o import do Presidio).
- [ ] T014 [P] [DbC] — Teste [AC5] em `tests/security/recognizers/test_br_cpf.py::test_valid_cpf_detected_score_above_threshold` — DbC: `BR_CPF.Post` (score ≥ 0.85 com dígito válido).
- [ ] T015 [P] [DbC] — Teste [AC6] em `tests/security/recognizers/test_br_cpf.py::test_invalid_digit_cpf_not_masked` (000.000.000-00) — DbC: `BR_CPF.Invariant` (`validation_callback` executado em 100% dos matches).
- [ ] T016 [P] — Teste [AC7] em `tests/security/recognizers/test_br_cnpj.py::test_valid_cnpj_detected`.
- [ ] T017 [P] — Teste [AC8] em `tests/security/recognizers/test_br_rg.py::test_rg_pattern_detected`.
- [ ] T018 [P] — Teste [AC9] em `tests/security/recognizers/test_br_phone.py::test_br_phone_patterns_detected` (com e sem parênteses, com e sem 9).
- [ ] T019 [P] — Teste [AC10] em `tests/security/test_pii_mask.py::test_email_masked_as_placeholder`.
- [ ] T020 [P] — Teste [AC11] em `tests/security/test_pii_mask.py::test_date_time_detected_but_not_masked`.
- [ ] T021 [P] — Teste [AC12] em `tests/security/test_pii_mask.py::test_allow_list_bypasses_mask`.
- [ ] T022 [P] [DbC] — Teste de idempotência para [AC14] em `tests/security/test_pii_mask.py::test_idempotent_double_mask` (property-based via `pytest.parametrize` sobre amostras do corpus: `pii_mask(pii_mask(x).masked_text).masked_text == pii_mask(x).masked_text`) — DbC: `pii_mask.Invariant` (idempotência).
- [ ] T023 [P] — Teste de PII-em-logs em `tests/security/test_pii_mask.py::test_no_raw_pii_in_logs` (capture caplog).
- [ ] T025 [P] [DbC] — Teste [AC15] em `tests/security/test_guards.py::test_text_over_100kb_rejected` (text de 101 KB → `PIIError(code="E_PII_TEXT_SIZE")`; Presidio nunca chamado — mock assert) — DbC: `pii_mask.Pre` (text size).
- [ ] T026 [P] [DbC] — Teste [AC16] em `tests/security/test_guards.py::test_allow_list_over_50_rejected` (`allow_list=["a"]*51` → `PIIError(code="E_PII_ALLOW_LIST_SIZE")`) — DbC: `pii_mask.Pre` (allow_list size).
- [ ] T027 [P] [DbC] — Teste [AC17] em `tests/security/test_guards.py::test_pii_mask_timeout` (monkey-patch do motor Presidio com `sleep(6)` → `PIIError(code="E_PII_TIMEOUT")`) — DbC: `pii_mask.Post` (timeout).
- [ ] T028 [P] [DbC] — Teste [AC18] em `tests/security/test_logging.py::test_no_raw_pii_in_module_logs` (roda `pii_mask` em sample com CPF/nome; caplog não contém nenhum padrão PII de ARCHITECTURE; contém `entity_type` e `sha256_prefix` de 8 chars) — DbC: `MaskedResult.entities.Invariant` + ADR-0008 no-PII-in-logs.
- [ ] T024 — Rodar `uv run pytest tests/security/` e confirmar que **todos** os testes falham (RED).

## Implementation (GREEN)

- [ ] T030 — Implementar `security/errors.py` com `PIIError` (`E_PII_ENGINE`, `E_PII_LANGUAGE`).
- [ ] T031 — Implementar `security/models.py` com `EntityHit` (entity_type/start/end/score/sha256_prefix) e `MaskedResult` — atende AC2.
- [ ] T032 — Implementar `security/engine.py` com `@lru_cache` de `AnalyzerEngine` e `AnonymizerEngine`; trata falha de inicialização como `PIIError(E_PII_ENGINE)` (AC4).
- [ ] T033 [P] — Implementar `security/recognizers/br_cpf.py` combinando regex + `pycpfcnpj.cpf.validate` com score boost (AC5, AC6).
- [ ] T034 [P] — Implementar `security/recognizers/br_cnpj.py` análogo (AC7).
- [ ] T035 [P] — Implementar `security/recognizers/br_rg.py` com regex (AC8).
- [ ] T036 [P] — Implementar `security/recognizers/br_phone.py` com regex DDD+9 dígitos (AC9).
- [ ] T037 — Registrar todos os recognizers no `AnalyzerEngine` via `registry.add_recognizer(...)` em `engine.py`.
- [ ] T038 — Implementar `security/__init__.py::pii_mask(text, language, allow_list)` com pipeline completo: validação idioma → engine → analyze → filter allow_list → anonymize → construir `MaskedResult` com `sha256_prefix` por entidade (AC1, AC2, AC10, AC11, AC12).
- [ ] T039 — Aplicar mesmo mecanismo para política `DATE_TIME` (omitir do dict `operators` → default keep) (AC11).
- [ ] T040 — Rodar `uv run pytest tests/security/ --cov=security --cov-fail-under=80` e confirmar verde + cobertura (AC13).

## Refactor

- [ ] T050 — Extrair `security/_normalize.py` se os recognizers duplicarem lógica de limpar pontuação antes de `pycpfcnpj.validate`.
- [ ] T051 — Revisar docstrings Google-style em todas as funções públicas + `pii_mask`.
- [ ] T052 — Rodar `uv run ruff check .` + `uv run mypy --strict security/` até zero warnings.

## Evidence

- [ ] T090 — Capturar em `docs/EVIDENCE/0005-pii-guard.md`: `uv run pytest tests/security/ --cov`, relatório ≥ 80 %, log auditoria de exemplo (com sha256_prefix, sem valor cru).
- [ ] T091 — Anexar diff antes/depois de `pii_mask` em texto real de pedido médico (sintético) como prova de AC1.

## Paralelismo

`[P]` em setup (T005) e tests (T010–T023) amplo — arquivos distintos. Implementation: T033–T036 (quatro recognizers, arquivos distintos) totalmente paralelizáveis; T030–T032 sequenciais por dependência; T037 precisa dos 4 recognizers + engine; T038 é integração; T039 e T040 finais.
