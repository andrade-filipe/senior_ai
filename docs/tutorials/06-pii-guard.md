# Tutorial 06 — PII Guard (`security/`)

Este tutorial mostra como usar a camada PII do desafio: entender o que ela faz,
chamar `pii_mask()` a partir de um script Python, adicionar uma entidade nova e
rodar a suíte de testes. Todo o código do módulo vive em `security/`.

---

## 1. Objetivo

Ao final deste tutorial você será capaz de:

- Entender o papel do `security/` (dupla camada —
  [ADR-0003](../adr/0003-pii-double-layer.md)).
- Invocar `pii_mask(text)` e interpretar o `MaskedResult`.
- Usar `allow_list` para preservar termos de domínio.
- Plugar `make_pii_callback()` em um agente ADK.
- Adicionar um recognizer customizado.
- Rodar a suíte de testes com cobertura.

---

## 2. Pré-requisitos

- Python `3.12` (o `pyproject.toml` fixa `>=3.12,<3.13`).
- `uv` instalado (stack fechada — [ADR-0005](../adr/0005-dev-stack.md)).
- Nenhum serviço Docker precisa estar em pé para uso local da lib.

Instalação:

```bash
cd security
uv sync
uv run python -m spacy download pt_core_news_lg
```

> **Nota**: o `uv sync` instala `presidio-analyzer`, `presidio-anonymizer`,
> `spacy`, `pycpfcnpj` e `pydantic` conforme `security/pyproject.toml`.
> O **modelo spaCy `pt_core_news_lg` NÃO é instalado automaticamente** — é
> preciso rodar o `spacy download` manualmente (ou via Dockerfile de um
> serviço consumidor). Se o modelo estiver ausente, `pii_mask()` levanta
> `PIIError(code="E_PII_ENGINE")` com o comando corretivo no campo `hint`.

Para análise em inglês (opcional): `uv run python -m spacy download en_core_web_lg`.

---

## 3. Como invocar

Exemplo mínimo em Python:

```python
from security import pii_mask

masked = pii_mask(
    "João da Silva CPF 111.444.777-35 telefone (11) 98765-4321"
)
print(masked.masked_text)
# <PERSON> CPF <CPF> telefone <PHONE>

for hit in masked.entities:
    print(hit.entity_type, hit.score, hit.sha256_prefix)
```

A função recebe `text: str`, `language: str = "pt"`, `allow_list: list[str] | None = None`
e retorna um `MaskedResult` contendo `masked_text` e `entities: list[EntityHit]`.
Cada `EntityHit` carrega apenas `entity_type`, `start`, `end`, `score` e os
primeiros 8 caracteres de `sha256(raw_value)` — **nunca o valor cru**
(invariante em `security/security/models.py`).

---

## 4. Contratos resumidos

A camada é dupla, por exigência de [ADR-0003](../adr/0003-pii-double-layer.md):

- **Layer 1 — OCR MCP**: chamada em `ocr_mcp/ocr_mcp/server.py` no
  handler `_do_ocr`, antes da tool response. A API de agendamento nunca
  enxerga PII crua.
- **Layer 2 — agente ADK**: `generated_agent/agent.py` aplica
  `make_pii_callback(allow_list=[])` em `before_model_callback`,
  reanalisando todo o prompt antes do envio ao Gemini.

Detalhes das entidades (placeholders, `DATE_TIME` mantida, guardrails de
tamanho) estão em [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) § "Lista
definitiva de entidades PII" e a spec completa em
[`docs/specs/0005-pii-guard/spec.md`](../specs/0005-pii-guard/spec.md).

Guardrails ativos ([ADR-0008](../adr/0008-robust-validation-policy.md)):

| Guardrail | Cap | Erro levantado |
|---|---|---|
| Tamanho do texto | 100 KB | `E_PII_TEXT_SIZE` |
| Tamanho da allow-list | 1 000 itens | `E_PII_ALLOW_LIST_SIZE` |
| Tempo de processamento | 5 s (hard-kill) | `E_PII_TIMEOUT` |
| Idioma suportado | `pt`/`en` | `E_PII_LANGUAGE` |
| Inicialização do motor | — | `E_PII_ENGINE` |

---

## 5. Exemplos completos

### 5.1 Cobertura das entidades

```python
from security import pii_mask

text = (
    "Paciente Maria Silva, CPF 111.444.777-35, RG 12.345.678-9, "
    "CNPJ 11.222.333/0001-81, tel (11) 98765-4321, "
    "email maria@exemplo.com.br. Coleta em 01/05/2026."
)
print(pii_mask(text, language="pt").masked_text)
# Paciente <PERSON>, CPF <CPF>, RG <RG>, CNPJ <CNPJ>,
# tel <PHONE>, email <EMAIL>. Coleta em 01/05/2026.
```

`DATE_TIME` (`01/05/2026`) é **detectado mas não mascarado** — datas
clínicas são mantidas por decisão explícita de produto (AC11 da spec).

### 5.2 Idempotência (AC14)

```python
once = pii_mask("CPF 111.444.777-35", language="pt").masked_text
twice = pii_mask(once, language="pt").masked_text
assert once == twice  # "CPF <CPF>"
```

Aplicar a máscara duas vezes produz o mesmo resultado. A implementação
usa um filtro regex (`_PLACEHOLDER_RE` em `security/security/guard.py`)
que descarta qualquer match de Presidio totalmente contido em um
placeholder já presente (ex.: `EMAIL` dentro de `<EMAIL>` seria
redetectado como `PERSON` e resultaria em `<<PERSON>>` sem esse filtro).

### 5.3 `allow_list` — preservar termos de domínio

```python
from security import pii_mask

r = pii_mask(
    "Solicito Ciclo Menstrual e Hemograma para HospitalXYZ",
    language="pt",
    allow_list=["Ciclo Menstrual", "Hemograma", "HospitalXYZ"],
)
print(r.masked_text)
# Solicito Ciclo Menstrual e Hemograma para HospitalXYZ
```

Comparação é case-insensitive e exige match exato do span. Use para
nomes de exames, instituições e termos médicos que poderiam disparar
falso-positivo de `PERSON`.

### 5.4 Plugar no ADK

```python
from google.adk.agents import LlmAgent
from security import make_pii_callback

agent = LlmAgent(
    name="triagem",
    model="gemini-2.5-flash",
    instruction="...",
    tools=[...],
    before_model_callback=make_pii_callback(allow_list=["HospitalXYZ"]),
)
```

O callback retornado por `make_pii_callback()` itera sobre
`llm_request.contents[*].parts[*].text` e aplica `pii_mask()` in-place.
Ele nunca levanta — erros viram log `pii.callback.error` e o texto é
substituído pelo sentinela `"<REDACTED - PII guard error>"`
(implementação em `security/security/callback.py`).

---

## 6. Troubleshooting

### CPF com dígito inválido não é mascarado

`CPF 000.000.000-00` passa pelo regex mas falha no DV via `pycpfcnpj`.
O recognizer atribui `score=0.1`; mesmo após o boost `+0.35` do
`LemmaContextAwareEnhancer`, o final `0.45` fica abaixo do
`score_threshold=0.5` em `guard.py` e o match é descartado —
**comportamento correto** (AC6). Ver
[`docs/EVIDENCE/0005-pii-guard.md`](../EVIDENCE/0005-pii-guard.md).

### Timeout (`E_PII_TIMEOUT`)

Textos gigantes ou spaCy preso disparam o hard timeout de 5 s
([ADR-0008](../adr/0008-robust-validation-policy.md)). `pii_mask()`
chama `pool.terminate()` e levanta `PIIError(code="E_PII_TIMEOUT")`.
Divida o texto em pedaços menores ou investigue a saúde do modelo.

### `<<PERSON>>` duplicado

Versões antigas geravam `<<PERSON>>` no segundo pass. O fix é o filtro
`_drop_results_in_placeholder_spans()` em `security/security/guard.py`,
que descarta spans totalmente contidos em placeholders já presentes. Se
reaparecer, confirme que está na versão atual do módulo.

### Modelo spaCy ausente

Erro: `PIIError(code="E_PII_ENGINE")`. A mensagem traz o comando exato
no campo `hint`:

```bash
uv run python -m spacy download pt_core_news_lg
```

Para análise em inglês: `en_core_web_lg`.

### `allow_list` com mais de 1 000 itens

Levanta `PIIError(code="E_PII_ALLOW_LIST_SIZE")` antes de tocar no
Presidio. O cap é guardrail de [ADR-0008](../adr/0008-robust-validation-policy.md).
Revise a lista — provavelmente há oportunidade de usar categorias
canônicas em vez de enumerar sinônimos.

---

## 7. Onde estender

Os quatro recognizers brasileiros vivem em
`security/security/recognizers/`:

- `br_cpf.py` — regex + validação de DV via `pycpfcnpj`.
- `br_cnpj.py` — regex + validação de DV via `pycpfcnpj`.
- `br_rg.py` — regex puro (UFs variam, não há DV universal).
- `br_phone.py` — regex DDD + 8/9 dígitos.

Para adicionar uma nova entidade BR (ex.: `BR_CNS` — Cartão Nacional de
Saúde):

1. Copie um dos recognizers existentes como modelo
   (`br_cpf.py` se houver DV, `br_rg.py` se for regex puro).
2. Registre a classe em `security/security/recognizers/__init__.py`
   (lista `get_br_recognizers()`).
3. Adicione o placeholder em `_PLACEHOLDERS` dentro de
   `security/security/guard.py` e o entity-type em `_ENTITIES`.
4. Atualize `docs/ARCHITECTURE.md` § "Lista definitiva de entidades PII".
5. Escreva testes RED primeiro (caso positivo + negativo) em
   `security/tests/` — test-first é obrigatório aqui
   ([ADR-0004](../adr/0004-sdd-tdd-workflow.md)).
6. Rode a suíte:

```bash
cd security
uv run pytest --cov=security --cov-report=term-missing -v
```

O plano de engenharia completo (tarefas, critérios de aceitação,
checkpoints) está em
[`docs/specs/0005-pii-guard/plan.md`](../specs/0005-pii-guard/plan.md).
