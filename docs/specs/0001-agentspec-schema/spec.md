---
id: 0001-agentspec-schema
title: Schema Pydantic `AgentSpec` e validação do JSON de entrada do transpilador
status: implemented
linked_requirements: [R01]
owner_agent: software-architect
created: 2026-04-18
implemented: 2026-04-18
evidence: docs/EVIDENCE/0001-agentspec-schema.md
commit: 9396def
---

## Problema

O transpilador (Bloco 2) recebe um `spec.json` e precisa rejeitar entradas inválidas **antes** de renderizar qualquer template. Sem um schema formal, erros de input viram ou código Python inválido ou falhas tardias no `ast.parse`, com mensagens cripticas para quem escreveu o spec.

- O que falta hoje? Um modelo Pydantic v2 que congele o formato do `AgentSpec` conforme [ADR-0006](../../adr/0006-spec-schema-and-agent-topology.md) e dê mensagens de erro acionáveis.
- Quem é afetado? Qualquer usuário (humano ou automação) que produza `spec.json`; o próprio transpilador, que depende dessa validação para ser determinístico.
- Por que importa agora? É a fundação do Bloco 2 — transpilador não parte sem o schema pronto. Também é a fronteira pública do produto (avaliador escreve JSON contra ela).

## User stories

- Como **autor de spec**, quero mensagens de erro claras quando meu JSON está inválido para corrigir o arquivo rapidamente sem ler o código do transpilador.
- Como **transpiler-engineer**, quero um modelo Pydantic único e imutável para instanciar o pipeline de geração com garantia de tipos.
- Como **code-reviewer**, quero que qualquer campo fora do schema seja rejeitado por construção para não precisar caçar drift em PRs.

## Critérios de aceitação

- [AC1] Dado um JSON idêntico a `spec.example.json` de [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Schema Pydantic do JSON spec", quando o validador roda, então retorna uma instância `AgentSpec` sem erros.
- [AC2] Dado um JSON com campo `model: "gpt-4"`, quando o validador roda, então levanta `TranspilerError` com `code="E_TRANSPILER_SCHEMA"` e mensagem citando o campo `model` e os valores aceitos (`gemini-2.5-flash`).
- [AC3] Dado um JSON com `name: "Invalid Name"` (espaço, maiúsculas), quando o validador roda, então falha com `E_TRANSPILER_SCHEMA` e mensagem apontando o regex `^[a-z0-9][a-z0-9-]*$`.
- [AC4] Dado um JSON com campo extra `memory_type: "vector"` (fora do schema congelado), quando o validador roda, então falha com `E_TRANSPILER_SCHEMA` (Pydantic `extra="forbid"`) e cita o campo desconhecido.
- [AC5] Dado um JSON sem `mcp_servers` ou `http_tools`, quando o validador roda, então falha apontando o campo obrigatório ausente.
- [AC6] Dado um JSON com `mcp_servers[0].url = "not-a-url"`, quando o validador roda, então falha com erro que cita o índice (`mcp_servers.0.url`) e o motivo (URL malformada).
- [AC7] Dado qualquer `AgentSpec` válido, quando serializado via `model_dump_json()`, então o resultado é JSON parseável e round-trips de volta para uma instância equivalente.
- [AC8] Cobertura de testes no módulo `transpiler/schema.py` ≥ 80 % (ADR-0004).
- [AC9] Dado um JSON com `AgentSpec.mcp_servers=[{"name":"x",...},{"name":"x",...}]` (dois itens com mesmo `name`), quando o validador roda, então levanta `ValidationError` / `TranspilerError(code="E_TRANSPILER_SCHEMA")` com mensagem apontando o campo `name` duplicado — `name` é identificador único entre irmãos da mesma `AgentSpec` (invariante do `McpServerSpec`).
- [AC10] Dado um JSON com `mcp_servers[]` de 11 itens (ou `http_tools[]` de 21, ou `tool_filter[]` de 51), quando o validador roda, então levanta `TranspilerError(code="E_TRANSPILER_SCHEMA")` citando o campo e o cap aplicável (10 / 20 / 50) conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md).
- [AC11] Dado um JSON com `name`, `description` ou `instruction` > 500 chars (ou URL > 2048 chars), quando o validador roda, então levanta `TranspilerError(code="E_TRANSPILER_SCHEMA")` citando o campo estourado e o cap.
- [AC12] Dado um arquivo `spec.json` > 1 MB (medido em bytes antes de `json.loads`), quando `load_spec(path)` roda, então levanta `TranspilerError(code="E_TRANSPILER_SCHEMA")` com mensagem "spec.json excede 1 MB" — a leitura do arquivo é abortada antes do parse JSON.
- [AC13] Dado um `TranspilerError` produzido pela CLI, quando inspecionado, então serializa como o shape canônico de ADR-0008: stderr emite uma linha por campo (`code`, `message`, `hint`, `path`, `context`) e exit code ≠ 0.

## Robustez e guardrails

### Happy Path

Um `spec.json` pequeno e bem-formado (< 1 MB, listas dentro dos caps, `model="gemini-2.5-flash"`, `name` casando regex) é passado a `load_spec(source)` → retorna uma `AgentSpec` imutável, round-trip estável via `model_dump_json()`.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| `mcp_servers[]` > 10 itens | rejeitar no validador | `E_TRANSPILER_SCHEMA` | AC10 |
| `http_tools[]` > 20 itens | rejeitar no validador | `E_TRANSPILER_SCHEMA` | AC10 |
| `tool_filter[]` > 50 itens | rejeitar no validador | `E_TRANSPILER_SCHEMA` | AC10 |
| `name`/`description`/`instruction` > 500 chars | rejeitar no validador | `E_TRANSPILER_SCHEMA` | AC11 |
| URL > 2048 chars | rejeitar no validador | `E_TRANSPILER_SCHEMA` | AC11 |
| `spec.json` > 1 MB | rejeitar em bytes antes de `json.loads` | `E_TRANSPILER_SCHEMA` | AC12 |
| `model` fora de allowlist | rejeitar pelo `Literal` | `E_TRANSPILER_SCHEMA` | AC2 |
| Campo extra fora do schema | rejeitar via `extra="forbid"` | `E_TRANSPILER_SCHEMA` | AC4 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| `mcp_servers[]` | 10 itens | `E_TRANSPILER_SCHEMA` | AC10 |
| `http_tools[]` | 20 itens | `E_TRANSPILER_SCHEMA` | AC10 |
| `tool_filter[]` | 50 itens | `E_TRANSPILER_SCHEMA` | AC10 |
| `name`, `description`, `instruction` | 500 chars | `E_TRANSPILER_SCHEMA` | AC11 |
| URL (`url`, `base_url`, `openapi_url`) | 2048 chars | `E_TRANSPILER_SCHEMA` | AC11 |
| `spec.json` (bytes do arquivo) | 1 MB | `E_TRANSPILER_SCHEMA` | AC12 |

### Security & threats

- **Ameaça**: spec maligno com strings enormes causa alocação descontrolada na render do Bloco 2.
  **Mitigação**: cap de 500 chars em strings do spec + cap de 1 MB no arquivo, ambos cobertos por AC11 e AC12.
- **Ameaça**: lista de `tool_filter` imensa enfia centenas de entradas em `McpToolset`, aumentando superfície de ataque.
  **Mitigação**: cap de 50 itens (AC10).
- **Ameaça**: mensagens Pydantic default vazam jargão em EN no stderr da CLI.
  **Mitigação**: shape canônico ADR-0008 em `TranspilerError` com `message` e `hint` em PT-BR (AC13).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC1, AC4 | `AgentSpec` | Invariant |
| AC6, AC9 | `McpServerSpec` | Invariant |
| AC7 | `load_spec(source)` | Post |
| AC10, AC11 | `AgentSpec` | Invariant (guardrails ADR-0008) |
| AC12 | `load_spec(source)` | Pre (cap de 1 MB antes de parse) |

## Requisitos não-funcionais

- **Estabilidade do contrato**: qualquer mudança em campos de `AgentSpec` exige ADR nova supersedendo ADR-0006.
- **Erros acionáveis**: toda falha de validação carrega `code`, `message` em PT-BR e `hint` conforme a taxonomia em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Taxonomia de erros".
- **Determinismo**: o mesmo JSON produz a mesma mensagem de erro entre execuções (útil para snapshots de testes).
- **Type-check strict**: `mypy --strict` passa em `transpiler/` (ADR-0005 / GUIDELINES).

## Clarifications

*(nenhuma)*

## Fora de escopo

- Renderização de templates Jinja2 ou geração de código (Bloco 2).
- CLI `python -m transpiler` (Bloco 2).
- Suporte a topologias `SequentialAgent`/`ParallelAgent` (ADR-0006 deixa explícito: exige ADR nova).
- Validação semântica cruzada (ex.: "o `tool_filter` referencia uma tool que existe no servidor"). Schema valida forma, não presença remota.
