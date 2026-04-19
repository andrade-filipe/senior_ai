---
id: 0002-transpiler-mvp
title: Transpilador MVP — Jinja2 + generator + CLI com gate `ast.parse`
status: implemented
linked_requirements: [R01]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O desafio exige um transpilador que receba um `spec.json` válido e gere um pacote Python executável com um agente ADK. Sem esse bloco, nada roda — o Bloco 6 (agente) não existe, o Bloco 7 (compose) não tem o que orquestrar. O transpilador precisa ser **determinístico**, **idiomático** e **nunca** emitir Python inválido.

- O que falta hoje? A implementação do renderizador Jinja2, da CLI, da ordem de escrita dos arquivos, do gate `ast.parse` e da integração com o schema do Bloco 1.
- Quem é afetado? `transpiler-engineer` (executa), `adk-mcp-engineer` (consome o `generated_agent/`), avaliador (roda a CLI).
- Por que importa agora? É o artefato principal do desafio e fronteira pública do produto.

## User stories

- Como **autor de spec**, quero rodar `python -m transpiler ./spec.json -o ./generated_agent` e obter um pacote Python pronto para `adk run`.
- Como **avaliador**, quero que o mesmo `spec.json` produza **byte-a-byte** o mesmo `generated_agent/` em qualquer máquina.
- Como **transpiler-engineer**, quero que o transpilador **falhe alto** quando um template render emite Python inválido, em vez de passar para rodar e explodir na execução do agente.

## Critérios de aceitação

- [AC1] Dado `spec.example.json` válido e o comando `python -m transpiler ./spec.example.json -o ./out`, quando a CLI roda, então o diretório `./out/generated_agent/` contém pelo menos: `__init__.py`, `agent.py`, `requirements.txt`, `Dockerfile`, `.env.example`.
- [AC2] Dado o mesmo input de AC1, quando a CLI é executada duas vezes consecutivas em ambientes limpos, então todos os arquivos de saída são **byte-a-byte idênticos** (determinismo).
- [AC3] Dado o `agent.py` gerado, quando `ast.parse(open("agent.py").read())` é executado, então não levanta `SyntaxError` (gate ADR-0002).
- [AC4] Dado um `spec.json` inválido contra o schema do Bloco 1, quando a CLI roda, então sai com código de retorno `!= 0` e imprime em stderr mensagem com `code=E_TRANSPILER_SCHEMA`.
- [AC5] Dado um template corrompido propositalmente que emite Python inválido, quando a CLI roda, então falha com `code=E_TRANSPILER_SYNTAX` e cita o arquivo de saída que falhou no `ast.parse`.
- [AC6] Dado o `agent.py` gerado, quando inspecionado, então contém: `from google.adk.agents import LlmAgent`, instanciação de `McpToolset(connection_params=StreamableHTTPConnectionParams(url=...))` para cada item em `mcp_servers`, e referência a `before_model_callback` quando `guardrails.pii.enabled=True` (ADR-0001, ADR-0003, ADR-0006).
- [AC7] Dado o pacote `requirements.txt` gerado, quando inspecionado, então lista `google-adk`, `mcp[cli]` e (se PII ligado) o módulo `security` (instalado por path local ou referência de pacote, definido no plan).
- [AC8] Dado um `spec.json` com `tool_filter` não vazio para um MCP server, quando gerado, então o `McpToolset` correspondente carrega o parâmetro `tool_filter=[...]`.
- [AC9] Dado o pacote gerado, quando executada a suíte de snapshot (`pytest-regressions`), então o diff contra o snapshot dourado é vazio.
- [AC10] Cobertura de testes em `transpiler/` ≥ 80 % (ADR-0004).
- [AC11] Dado `output_dir` apontando para path traversal (ex.: `../../etc`, `/etc`, path absoluto fora do cwd), quando a CLI roda, então rejeita antes de render com `TranspilerError(code="E_TRANSPILER_RENDER")` e mensagem "output_dir fora do projeto".
- [AC12] Dado o template Jinja2 renderiza com `autoescape=False` (emite Python, não HTML), quando valores do spec que viram identifier Python (ex.: `name`) são substituídos, então passam por allow-list regex antes de entrar no template — defende contra injeção de template se um spec maligno tentar `"}}; import os; os.system(...)"` como nome (reforço explícito de AC3 do Bloco 1).
- [AC13] Dado o `agent.py` renderizado excede 100 KB, quando inspecionado pós-render, então levanta `TranspilerError(code="E_TRANSPILER_RENDER_SIZE")` conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md) — indica spec patológico, não código correto.

## Robustez e guardrails

### Happy Path

`python -m transpiler ./spec.example.json -o ./out` com spec válido (Bloco 1 aprovou) → `./out/generated_agent/` contém `__init__.py`, `agent.py`, `requirements.txt`, `Dockerfile`, `.env.example`, cada `.py` passa `ast.parse`, byte-a-byte idêntico entre runs.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| `output_dir` = `../../etc` ou path absoluto fora do cwd | rejeitar antes de render | `E_TRANSPILER_RENDER` | AC11 |
| Spec maligno com `name` contendo injeção de template | rejeita pelo regex do Bloco 1 (AC3) + allow-list no template | `E_TRANSPILER_SCHEMA` | AC12 |
| `agent.py` renderizado > 100 KB | rejeita pós-render | `E_TRANSPILER_RENDER_SIZE` | AC13 |
| Template corrompido gera Python inválido | gate `ast.parse` | `E_TRANSPILER_SYNTAX` | AC5 |
| Spec inválido (schema Bloco 1) | repassa erro do Bloco 1 | `E_TRANSPILER_SCHEMA` | AC4 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| `output_dir` resolvido | dentro do cwd (ou subpath do projeto) | `E_TRANSPILER_RENDER` | AC11 |
| `agent.py` gerado | 100 KB | `E_TRANSPILER_RENDER_SIZE` | AC13 |

### Security & threats

- **Ameaça**: path traversal via `--output` aponta para `/etc` ou `~/.ssh` e sobrescreve arquivos do usuário.
  **Mitigação**: normalizar `output_dir` e checar `Path(output_dir).resolve().is_relative_to(Path.cwd())` antes de write (AC11).
- **Ameaça**: template injection — spec maligno insere código Python nos valores renderizados sem escape (Jinja2 `autoescape=False` é necessário para gerar `.py`, mas abre a porta).
  **Mitigação**: allow-list regex sobre os campos que viram identifiers Python; `ast.parse` como gate final catch-all (AC12 + AC3).
- **Ameaça**: spec patológico (listas enormes, strings enormes) explode render em arquivo de MBs.
  **Mitigação**: caps do Bloco 1 (AC10/AC11 de lá) + cap pós-render de 100 KB em `agent.py` (AC13).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC2 | `render(spec, output_dir)` | Invariant (determinismo) |
| AC3 | `render(spec, output_dir)` | Post (gate `ast.parse`) |
| AC11 | `render(spec, output_dir)` | Pre (`output_dir` dentro do cwd) |
| AC13 | `render(spec, output_dir)` | Post (cap 100 KB pós-render) |

## Requisitos não-funcionais

- **Determinismo**: a ordem das chaves em dicts, a ordem de imports e a ordem de listas renderizadas são estáveis entre execuções (sem `set()` iterado).
- **Mensagens de erro**: todos os erros seguem a taxonomia (`E_TRANSPILER_SCHEMA`, `E_TRANSPILER_RENDER`, `E_TRANSPILER_SYNTAX`) de [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
- **CLI UX**: `--help` documenta flags; código de saída 0 em sucesso, 1 em falha de schema, 2 em falha de render, 3 em falha de `ast.parse`.
- **Type-check strict**: `mypy --strict` passa em `transpiler/` (ADR-0005 / GUIDELINES).

## Clarifications

*(nenhuma — ADR-0002 congela Jinja2 + `ast.parse`; `ruff format` no output é explicitamente opcional.)*

## Fora de escopo

- Schema Pydantic (Bloco 1).
- Implementação das tools MCP e da API (Blocos 3 e 4).
- `ruff format` automático no output — ADR-0002 deixa explícito que é opcional e não é MVP.
- Geração de tests do agente — tests ficam no repo do transpilador (snapshot), não embarcados no pacote gerado.
- Suporte a `SequentialAgent`/`ParallelAgent` — ADR-0006.
