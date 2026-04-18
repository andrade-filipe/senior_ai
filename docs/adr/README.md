# Architectural Decision Records (ADRs)

Registros de decisões arquiteturais aceitas ao longo do desenvolvimento. ADRs são **imutáveis após aceite**: mudanças geram uma ADR nova com status `accepted` que marca a anterior como `superseded`.

## Índice

*(nenhuma ADR aceita ainda — o projeto está na fase de preparação)*

| # | Título | Status | Data |
|---|---|---|---|

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
