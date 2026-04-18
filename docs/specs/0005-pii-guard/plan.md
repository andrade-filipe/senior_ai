---
id: 0005-pii-guard
status: proposed
---

## Abordagem técnica

Módulo `security/` com uma única função pública `pii_mask` e quatro custom recognizers BR escritos à mão conforme nota de correção de [ADR-0003](../../adr/0003-pii-double-layer.md). Motor Presidio com engine spaCy PT-BR (`pt_core_news_lg`). Dupla camada é responsabilidade dos consumidores (Blocos 3 e 6); este bloco entrega apenas a biblioteca. Guardrails de input, timeout e política "no-PII-in-logs" conforme [ADR-0008](../../adr/0008-robust-validation-policy.md).

```
security/
├── __init__.py         # reexporta pii_mask, MaskedResult, PIIError
├── engine.py           # inicialização do Presidio + cache
├── recognizers/
│   ├── br_cpf.py       # regex + pycpfcnpj.cpf.validate
│   ├── br_cnpj.py      # regex + pycpfcnpj.cnpj.validate
│   ├── br_rg.py        # regex (sem validação de dígito — UFs variam)
│   └── br_phone.py     # regex DDD + 9 dígitos
├── models.py           # MaskedResult, EntityHit
├── errors.py           # PIIError (E_PII_ENGINE, E_PII_LANGUAGE)
└── pyproject.toml
```

### Fluxo de `pii_mask`

1. Valida `language in {"pt", "en"}`; levanta `PIIError(E_PII_LANGUAGE)` se outro (AC3).
2. Obtém engine via cache singleton (`functools.lru_cache`); falha → `PIIError(E_PII_ENGINE)` com hint (AC4).
3. Remove tokens do `allow_list` da análise (inserindo em "deny list inversa" do Presidio ou pós-filtro).
4. Analisa: `AnalyzerEngine.analyze(text, language=language, entities=<lista de types>)`.
5. Mascara: `AnonymizerEngine.anonymize(text, analyzer_results, operators={"BR_CPF": OperatorConfig("replace", {"new_value": "<CPF>"}), ...})`.
6. Retorna `MaskedResult(masked_text, entities=[EntityHit(type, start, end, score, sha256_prefix)])`.

### Custom recognizers

Herdam de `presidio_analyzer.PatternRecognizer` ou `presidio_analyzer.EntityRecognizer` conforme complexidade:

- **`BR_CPF`**: regex `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` + `validation_callback = lambda m: pycpfcnpj.cpf.validate(m)`. Score base 0.6; +0.3 se validação de dígito passa.
- **`BR_CNPJ`**: regex `\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}` + `pycpfcnpj.cnpj.validate`.
- **`BR_RG`**: regex `\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]` — mais ambíguo, score base 0.5.
- **`BR_PHONE`**: regex `\(?\d{2}\)?\s?9?\d{4}-?\d{4}` (DDD + 8 ou 9 dígitos).

### Política `DATE_TIME`

Entidade `DATE_TIME` do Presidio é detectada mas operador `keep` (não mascara) — congelado em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII". Implementação: omite `DATE_TIME` do dict `operators` (default Presidio é keep se não configurado).

### Allow-list

Implementação: após o `analyze`, filtra `AnalyzerResult` cujo `text[start:end].lower()` case qualquer item do `allow_list` (case-insensitive). Mais simples que customizar Presidio e suficiente para AC12.

## Data models

```python
# security/models.py
class EntityHit(BaseModel):
    entity_type: str
    start: int
    end: int
    score: float
    sha256_prefix: str  # primeiros 8 chars do sha256 do valor cru — usado apenas em log de auditoria

class MaskedResult(BaseModel):
    masked_text: str
    entities: list[EntityHit]
```

```python
# security/errors.py
class PIIError(ChallengeError): ...
```

## Contratos

Função pública:

```python
def pii_mask(text: str, language: str = "pt", allow_list: list[str] | None = None) -> MaskedResult
```

Consumidores (documentação contratual, não implementação aqui):
- **Bloco 3** (`ocr-mcp`): chama antes de retornar da tool.
- **Bloco 6** (`generated_agent`): registra como `before_model_callback`.

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `pii_mask(text, language, allow_list)` | `language in {"pt", "en"}` (senão `PIIError(E_PII_LANGUAGE)`); `text` é `str` ≤ 100 KB UTF-8 (ADR-0008); `allow_list` ≤ 50 itens; timeout 5 s | `masked_text` **não contém** nenhum valor original detectado como entity; em falha, serializa erro no shape canônico ADR-0008 | idempotente: `pii_mask(pii_mask(x).masked_text).masked_text == pii_mask(x).masked_text` | AC1, AC2, AC14, AC15, AC16, AC17 | T010 `[DbC]`, T011 `[DbC]`, T022 `[DbC]`, T025 `[DbC]`, T026 `[DbC]`, T027 `[DbC]` |
| `MaskedResult.entities` | construção via `pii_mask` | lista de `EntityHit` com `entity_type`, posições, score, `sha256_prefix` | `entities[*]` **nunca** carrega `value` cru — só `sha256_prefix` de 8 chars (defesa contra log leak) | AC2, AC18 | T011 `[DbC]`, T028 `[DbC]` |
| `BR_CPF` recognizer | texto PT-BR | detectado com score ≥ 0.6; +0.3 se dígito verificador (via `pycpfcnpj.cpf.validate`) | `validation_callback` executado em 100 % dos matches regex | AC5, AC6 | T014 `[DbC]`, T015 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `presidio-analyzer` | `^2.2` | Motor de detecção (ADR-0003) | Regex puras (rejeitado — muitos FP/FN em PERSON) |
| `presidio-anonymizer` | `^2.2` | Operadores `replace` | Manual string slicing (rejeitado — frágil) |
| `spacy` + `pt_core_news_lg` | `spacy^3.7` | NER PT-BR | `pt_core_news_md` (menor mas perde recall) |
| `pycpfcnpj` | `^1.8` | Validação de dígito verificador (ADR-0003 ref) | Implementar cálculo em casa (rejeitado — reinventar) |

Download do modelo spaCy acontece no build Docker (Bloco 7): `python -m spacy download pt_core_news_lg`. Em dev, `uv run python -m spacy download pt_core_news_lg` uma vez.

## Riscos

| Risco | Mitigação |
|---|---|
| Modelo spaCy grande (~500 MB) infla imagem do `ocr-mcp`. | Aceitável no MVP; inspecionar tamanho no Bloco 7; se virar dor, trocar por `pt_core_news_md` via ADR. |
| PersonRecognizer do Presidio em PT é mais fraco que em EN. | Adicionar testes explícitos com nomes comuns brasileiros (João, Maria, Ana); ajustar threshold se FP alto. |
| `pycpfcnpj` pode não aceitar strings com pontuação. | Wrapper remove formatação antes de validar (regex `\D`). Testado em AC5, AC6. |
| Presidio aceita `entities` como allow-list e pode ignorar nosso BR_*. | Registrar `AnalyzerEngine(registry=registry)` com `registry.add_recognizer(...)` explícito para cada BR_*; teste unitário confirma (AC5, AC7). |

## Estratégia de validação

- **Test-first obrigatório** (ADR-0004, GUIDELINES § 4): todos os testes RED antes do GREEN. Cobertura ≥ 80 % gate (AC13).
- **Unit** por recognizer: `tests/security/recognizers/test_br_cpf.py` etc. — pelo menos um caso positivo + um negativo + um falso-positivo evitado (AC5, AC6, AC7, AC8, AC9).
- **Unit** do motor: `tests/security/test_engine.py` — inicialização OK, idioma inválido (AC3), deps quebradas (AC4, mockando import).
- **Unit** da API pública: `tests/security/test_pii_mask.py` — AC1, AC2, AC10, AC11, AC12.
- **Property-based** (opcional, stretch): `hypothesis` gerando CPFs válidos/inválidos para AC5/AC6.
- **Idempotência** (NFR): teste `assert pii_mask(pii_mask(x).masked_text).masked_text == pii_mask(x).masked_text`.
- **No-PII-in-logs**: teste com logger-capture garantindo que nenhum log do módulo contém o valor cru (AC2).
- **Cobertura**: `pytest --cov=security --cov-fail-under=80`; anexado em evidência.

**Estratégia de validação atualizada (ADR-0008)**:
- **Text size (AC15)**: guard no início de `pii_mask` — `len(text.encode("utf-8")) > 100 * 1024` → `PIIError(code="E_PII_TEXT_SIZE")`; ocorre antes de qualquer chamada ao motor.
- **Allow-list size (AC16)**: `len(allow_list) > 50` → `PIIError(code="E_PII_ALLOW_LIST_SIZE")`.
- **Timeout (AC17)**: envolver pipeline em `asyncio.wait_for(..., timeout=5.0)` ou `concurrent.futures` se mantido sync; timeout → `PIIError(code="E_PII_TIMEOUT")`.
- **No-PII-in-logs (AC18)**: todos os loggers do módulo usam apenas `entity_type`, `sha256_prefix`, contadores numéricos; teste `caplog` em T028 enforça regex que rejeita se o caplog contiver qualquer padrão PII definido em ARCHITECTURE.

## Dependências entre blocos

- **Totalmente independente** de outros blocos em código.
- Em termos de **spec/contrato**: depende apenas de ADR-0003 + [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII" e § "PII Guard" — frozen.
- **Bloqueia** Bloco 3 (OCR MCP, linha 1) e Bloco 6 (agente, linha 2) em código — ambos podem iniciar RED em paralelo usando stub temporário (ver Bloco 3 plan) mas GREEN depende deste.
