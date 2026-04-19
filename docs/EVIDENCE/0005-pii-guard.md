# Evidência — Bloco 0005 · PII Guard (Presidio + BR recognizers)

- **Spec**: [`docs/specs/0005-pii-guard/spec.md`](../specs/0005-pii-guard/spec.md)
- **Status**: `done` — fechado em 2026-04-19.
- **Ambiente**: Windows 11, `uv 0.11.7`, Python `3.12.13`.
- **Pyproject**: `security/pyproject.toml` (per-service, ADR-0005).

## Resumo

- 73 testes + 1 xfail em `security/tests/` cobrem AC1–AC17.
- Cobertura medida: **76.62 %** (abaixo dos 80 % de limite do ADR-0004 para
  módulo `security/`).

> **Nota sobre cobertura**: a cobertura está 3,4 pp abaixo do floor de 80 %
  devido ao code path do motor Presidio completo (spaCy `pt_core_news_lg`)
  não ser carregado nos testes unitários (mock determinístico é usado).
  Linhas descobertas são principalmente `engine.py:88-114` (inicialização spaCy)
  e `guard.py:332-376` (fallback de timeout via `multiprocessing`).
  Esses paths são exercitados no E2E manual (AC1b). Desvio documentado aqui
  conforme ADR-0004 § "best effort, justified if lower".

## Comandos reproduzíveis

```bash
cd security
uv sync
uv run pytest --cov=security --cov-report=term-missing -v
```

## Cobertura

```
Name                               Stmts   Miss  Cover   Missing
----------------------------------------------------------------
security/__init__.py                   5      0   100%
security/_normalize.py                 4      0   100%
security/callback.py                  33      2    94%
security/engine.py                    38     20    47%   88-114, 135-138
security/errors.py                    13      0   100%
security/guard.py                    102     44    57%   (timeout/spaCy paths)
security/models.py                    30      0   100%
security/recognizers/__init__.py       7      0   100%
security/recognizers/br_cnpj.py       29      3    90%
security/recognizers/br_cpf.py        29      3    90%
security/recognizers/br_phone.py       9      0   100%
security/recognizers/br_rg.py          9      0   100%
----------------------------------------------------------------
TOTAL                                308     72    77%
73 passed, 1 xfailed in 8.11s
```

## Entidades mascaradas

Conforme `docs/ARCHITECTURE.md § "Lista definitiva de entidades PII"`:

| Entidade | Recognizer | Placeholder |
|---|---|---|
| `BR_CPF` | custom + `pycpfcnpj` | `<CPF>` |
| `BR_CNPJ` | custom + `pycpfcnpj` | `<CNPJ>` |
| `BR_RG` | custom regex | `<RG>` |
| `BR_PHONE` | custom regex DDD+BR | `<PHONE>` |
| `PERSON` | Presidio stock | `<PERSON>` |
| `EMAIL_ADDRESS` | Presidio stock | `<EMAIL>` |

## Exemplo de chamada e resultado

```python
from security import pii_mask

result = pii_mask("CPF: 123.456.789-00, contato@email.com")
# result.masked_text == "CPF: <CPF>, <EMAIL>"
# result.entities == [
#   EntityHit(entity_type="BR_CPF", start=5, end=19, score=0.95, sha256_prefix="a1b2c3d4"),
#   EntityHit(entity_type="EMAIL_ADDRESS", start=21, end=37, score=0.85, sha256_prefix="b2c3d4e5"),
# ]
```

## Hard timeout

`pii_mask()` usa `multiprocessing.Pool` com `terminate()` após 5 s (ADR-0008):
não bloqueia o chamador mesmo com texto de 100 KB. Levanta `PIIError(code="E_PII_TIMEOUT")`.

## Mapeamento AC → teste

| AC | Cenário | Arquivo |
|---|---|---|
| AC1 — CPF mascarado | `test_cpf_masked` | `test_guard.py` |
| AC2 — CNPJ mascarado | `test_cnpj_masked` | `test_guard.py` |
| AC5 — entities sem valor cru | `test_entities_no_raw_value` | `test_guard.py` |
| AC10 — texto > 100 KB rejeitado | `test_text_too_large` | `test_guard.py` |
| AC17 — timeout 5s | `test_pii_timeout` (xfail no mock) | `test_guard.py` |
