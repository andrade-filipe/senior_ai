---
id: 0001-agentspec-schema
status: proposed
---

## Abordagem técnica

Implementar o pacote `transpiler/` com um submódulo `transpiler/schema.py` contendo as classes Pydantic v2 congeladas em [ADR-0006](../../adr/0006-spec-schema-and-agent-topology.md), uma exceção-base `TranspilerError` (herdando de `ChallengeError`) e uma função pública `load_spec(path_or_dict) -> AgentSpec` que centraliza leitura + validação + tradução de erros Pydantic em instâncias de `TranspilerError(code="E_TRANSPILER_SCHEMA", ...)` conforme taxonomia em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Taxonomia de erros".

Decisões complementares (sem ADR — operacionais):
- **`model_config = ConfigDict(extra="forbid")`** em cada BaseModel para capturar campos desconhecidos (AC4).
- **Validação de URL** via `AnyHttpUrl` em `McpServerSpec.url` e `HttpToolSpec.base_url` (satisfaz AC6).
- Mensagens de erro traduzidas para PT-BR a partir do `ValidationError` do Pydantic, mantendo `loc` (path do campo) como identificador técnico.
- **Guardrails de tamanho** conforme [ADR-0008](../../adr/0008-robust-validation-policy.md): caps aplicados via `Field(max_length=...)` / `Field(max_items=...)` em cada classe Pydantic (AC10, AC11); cap de 1 MB do arquivo é cheque em bytes **antes** de `json.loads` em `load_spec(path)` (AC12); serialização de `TranspilerError` para stderr da CLI segue o shape canônico (AC13).

## Data models

Cópia literal do schema em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Schema Pydantic do JSON spec" (não reescrever aqui — a fonte da verdade é ARCHITECTURE + ADR-0006). Adições locais:

```python
# transpiler/errors.py
class ChallengeError(Exception):
    code: str
    message: str
    hint: str | None

class TranspilerError(ChallengeError): ...
```

```python
# transpiler/schema.py — extras de infra (não mudam a forma pública)
class McpServerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    url: AnyHttpUrl
    tool_filter: list[str] | None = None
# ...idem para as outras classes
```

## Contratos

Nenhum contrato HTTP ou MCP aqui — este bloco expõe apenas a API Python:

- `transpiler.load_spec(source: str | Path | dict) -> AgentSpec`
- `transpiler.errors.TranspilerError`
- Classes Pydantic exportadas em `transpiler/__init__.py`: `AgentSpec`, `McpServerSpec`, `HttpToolSpec`, `PiiGuardSpec`, `GuardrailSpec`.

Consumidores diretos: Bloco 2 (transpilador MVP) importa estas classes.

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `AgentSpec` | input é `dict` pós-`json.loads` | instância imutável (`ConfigDict(extra="forbid")`) | `mcp_servers` não-vazia; `model` em allowlist fixada em ADR-0006; caps de lista e string conforme ADR-0008 | AC1, AC4, AC10, AC11 | T010 `[DbC]`, T013 `[DbC]`, T028 `[DbC]`, T029 `[DbC]` |
| `McpServerSpec` | `url` é string ≤ 2048 chars | `url` validada como `AnyHttpUrl` | `name` único entre irmãos da mesma `AgentSpec` | AC6, AC9, AC11 | T015 `[DbC]`, T027 `[DbC]`, T029 `[DbC]` |
| `load_spec(source)` | `source` é `str`/`Path` de JSON válido (≤ 1 MB) **ou** `dict` | retorno é `AgentSpec` totalmente validado | round-trip `model_dump_json() → load_spec()` é estável (idempotente); cap de 1 MB aplicado antes de `json.loads` (ADR-0008) | AC7, AC12 | T016 `[DbC]`, T030 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `pydantic` | `^2.6` | Schema, `ConfigDict(extra="forbid")`, `Literal` | `dataclasses` + valida manual (rejeitado — verboso e sem round-trip JSON) |
| `pytest` | `^8` | Framework de teste (GUIDELINES § 4) | — |
| `pytest-cov` | `^5` | Cobertura ≥ 80 % (ADR-0004) | — |

Zero deps runtime novas além de Pydantic, já no stack.

## Riscos

| Risco | Mitigação |
|---|---|
| Mensagens Pydantic default vazam jargão ("value is not a valid url") em inglês ao usuário final. | Wrapping em `TranspilerError` com mensagem em PT-BR + hint. Teste explícito (AC2, AC3) garante formato. |
| `AnyHttpUrl` do Pydantic 2 retorna `Url` (não `str`), pode quebrar consumidores. | Normalizar para `str` ao serializar no `model_dump_json` para o Jinja2 do Bloco 2. |
| Alguém adiciona campo no schema sem abrir ADR. | `extra="forbid"` + teste AC4 bloqueia silenciosamente; revisão humana percebe no PR. |

## Estratégia de validação

- **Unit tests** em `tests/transpiler/test_schema.py` cobrindo AC1–AC7 com casos positivos e negativos. Fixture JSON mínima literal de [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
- **Snapshot tests** do `model_dump_json()` do `spec.example.json` via `pytest-regressions` para garantir estabilidade do round-trip.
- **Cobertura**: `pytest --cov=transpiler.schema --cov-fail-under=80` — reporte anexado à evidência (AC8).
- **Test-first obrigatório** (ADR-0004): `qa-engineer` escreve os testes da seção RED antes de qualquer linha em `transpiler/schema.py`.

**Estratégia de validação atualizada (ADR-0008)**:
- Caps de listas (AC10) aplicados via `Field(max_length=10/20/50)` em `AgentSpec.mcp_servers`, `AgentSpec.http_tools`, `McpServerSpec.tool_filter`.
- Caps de string (AC11) via `Field(max_length=500)` em `name`, `description`, `instruction`; `Field(max_length=2048)` em `url`, `base_url`, `openapi_url`.
- Cap de 1 MB do arquivo `spec.json` (AC12) é cheque manual em bytes no início de `load_spec(path)` — antes de `path.read_text()` / `json.loads`. Mensagem do `TranspilerError` cita bytes observados vs cap.
- Shape canônico de erro (AC13) fica em helper de serialização em `transpiler/errors.py::format_challenge_error(exc) -> dict` reaproveitável pela CLI.

## Dependências entre blocos

- **Independente.** Pode ser implementado em paralelo com Blocos 3, 4, 5 porque não importa nada deles.
- **Bloqueia** o Bloco 2 (transpilador MVP) — não dá para renderizar templates sem validar o input antes.
- Em termos de spec/contrato, este bloco só depende de ADR-0006 e da seção "Schema Pydantic do JSON spec" de ARCHITECTURE — ambos **frozen** na fase de design.
