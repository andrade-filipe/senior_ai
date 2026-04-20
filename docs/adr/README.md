# Architectural Decision Records (ADRs)

Registros de decisões arquiteturais aceitas ao longo do desenvolvimento. ADRs são **imutáveis após aceite**: mudanças geram uma ADR nova com status `accepted` que marca a anterior como `superseded`.

## Índice

| # | Título | Status | Data |
|---|---|---|---|
| [0001](0001-mcp-transport-sse.md) | Transporte MCP via SSE | accepted | 2026-04-18 |
| [0002](0002-transpiler-jinja-ast.md) | Transpilador JSON → Python via Jinja2 + `ast.parse` | accepted | 2026-04-18 |
| [0003](0003-pii-double-layer.md) | PII mascarada em dupla camada (OCR + `before_model_callback`) | accepted | 2026-04-18 |
| [0004](0004-sdd-tdd-workflow.md) | Workflow SDD + TDD pragmático | accepted | 2026-04-18 |
| [0005](0005-dev-stack.md) | Stack de desenvolvimento (uv + Gemini + GitHub Actions) | accepted | 2026-04-18 |
| [0006](0006-spec-schema-and-agent-topology.md) | Schema do JSON spec + topologia do agente gerado | accepted *(parcialmente superseded por ADR-0009 no escopo do campo `model`; parcialmente superseded por ADR-0010 no escopo de tool call com argumento derivado de payload binário)* | 2026-04-18 |
| [0007](0007-rag-fuzzy-and-catalog.md) | RAG MCP via rapidfuzz + catálogo CSV | accepted | 2026-04-18 |
| [0008](0008-robust-validation-policy.md) | Robustez de validação — taxonomia de erros, guardrails e shape de resposta | accepted | 2026-04-18 |
| [0009](0009-runtime-config-via-env.md) | Configuração de runtime via variáveis de ambiente | accepted | 2026-04-20 |
| [0010](0010-preocr-invocation-pattern.md) | Pré-OCR invocado pelo CLI (CLI-orchestrated pre-step) | accepted | 2026-04-20 |

## Quando abrir uma ADR

Apenas o agente `software-architect` ou o usuário abre ADRs, nas situações:

- Um contrato público entre subsistemas muda (schema, URL, mensagem).
- Uma escolha de tecnologia tem alternativas não triviais.
- Uma decisão tem impacto em outros módulos e precisa ser comunicada.

Para decisões reversíveis/triviais, prefira documentar inline (commit, PR description, comentário no `docs/STATUS.md` interno).

## Numeração

ADRs começam em `0001` e seguem sequência estrita. O número **não é reaproveitado** quando uma ADR é `superseded`. Nome do arquivo: `NNNN-slug-curto.md`.

## Template

Copie e preencha ao criar uma nova ADR (`docs/adr/NNNN-slug.md`):

```markdown
# ADR-NNNN: Título curto da decisão

- **Status**: proposed | accepted | superseded by ADR-XXXX
- **Data**: YYYY-MM-DD
- **Autor(es)**: nome / agente

## Contexto

O que motivou a decisão? Qual problema, requisito ou restrição exige uma escolha?
Cite fontes (DESAFIO.md, GUIDELINES.md, incidente, issue, etc.).

## Alternativas consideradas

1. **Alternativa A** — breve descrição.
   - Prós: …
   - Contras: …
2. **Alternativa B** — …
3. **Alternativa C** — …

## Decisão

Qual alternativa foi escolhida, em termos explícitos.

## Consequências

- Positivas: …
- Negativas / débito técnico: …
- Impacto em outros subsistemas: …

## Referências

- Links para `ai-context/references/*.md` ou seções de `docs/ARCHITECTURE.md` relevantes.
- Links externos (docs oficiais, RFCs).
```

## Ciclo de vida de uma ADR

1. `proposed` — rascunho aberto para discussão (agente sozinho ou com o usuário).
2. `accepted` — aprovada; passa a valer; referenciada por commits relacionados.
3. `superseded by ADR-XXXX` — substituída; arquivo fica no histórico para rastreabilidade.

Nunca editamos o conteúdo de uma ADR `accepted`. Correções pequenas (typo, link quebrado) são toleráveis; mudanças de mérito pedem ADR nova.
