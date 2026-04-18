# Specs — Spec-Driven Development

Este diretório é o **artefato primário** do desenvolvimento. Cada bloco de implementação vive em `docs/specs/NNNN-<slug>/` com três arquivos: `spec.md`, `plan.md`, `tasks.md`. Código existe para satisfazer a spec — não o contrário.

Método formalizado em [ADR-0004](../adr/0004-sdd-tdd-workflow.md). Inspirado no [GitHub spec-kit](https://github.com/github/spec-kit) e no manifesto [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md), mas aplicado manualmente com os subagentes deste projeto.

## Regra de ouro

> **Specs não servem ao código; o código serve às specs.**

Quando a implementação divergir do spec, atualizamos o spec antes de consertar o código. Uma divergência não declarada é um bug de processo, não um atalho.

## Estrutura de um bloco

```
docs/specs/
├── README.md                    # este arquivo
└── NNNN-<slug>/
    ├── spec.md                  # o quê e por quê
    ├── plan.md                  # como (alto nível)
    └── tasks.md                 # passos executáveis
```

- `NNNN` é um contador global começando em `0001`; nunca reaproveitado.
- `<slug>` é curto, em inglês, kebab-case (ex.: `transpiler-schema`, `pii-guard`).
- Um bloco = uma fatia entregável de valor. Blocos muito grandes devem ser quebrados antes do checkpoint humano.

## Ciclo por bloco (resumo)

```
1. Requisito → 2. Spec → 3. Plan → 4. Tasks → [checkpoint humano #1]
                                                     ↓
9. Checkpoint humano #2 ← 8. Docs ← 7. Evidence ← 6. Review ← 5. Tests→Code
```

Detalhes, donos e entregáveis por passo: `ai-context/WORKFLOW.md`.

## Templates

Os três templates abaixo são copiados literalmente ao abrir um bloco novo. Campos no frontmatter são **obrigatórios** — o `code-reviewer` reprova specs que omitam qualquer um deles.

### Template `spec.md`

```markdown
---
id: NNNN-<slug>
title: <título curto e informativo>
status: draft | review | approved | implemented | superseded
linked_requirements: [R01, R05]   # IDs de docs/REQUIREMENTS.md
owner_agent: software-architect
created: YYYY-MM-DD
---

## Problema

Descrever o problema em termos do usuário ou do desafio. Sem jargão técnico quando possível. Responder:
- O que não funciona hoje / o que falta?
- Quem é afetado?
- Por que importa agora?

## User stories

- Como <papel>, eu quero <capacidade> para <valor>.
- Como <papel>, eu quero <capacidade> para <valor>.

## Critérios de aceitação

Cada critério é **verificável** — por teste automatizado ou inspeção objetiva. Numerar como `AC1`, `AC2`, … para que `tasks.md` possa referenciar.

- [AC1] Dado <contexto>, quando <ação>, então <resultado observável>.
- [AC2] …

## Requisitos não-funcionais

Desempenho, segurança, observabilidade, operabilidade. Usar números sempre que possível (ex.: "p95 < 200 ms").

## [NEEDS CLARIFICATION]

Lista explícita de ambiguidades conhecidas. Cada item vira uma pergunta ao usuário antes de `status: approved`. Specs com itens abertos aqui ficam em `status: review`.

- [ ] <pergunta>

## Fora de escopo

Explicitar o que **não** é tratado aqui. Evita escopo inflar durante implementação.
```

### Template `plan.md`

```markdown
---
id: NNNN-<slug>
status: proposed | approved | done
---

## Abordagem técnica

Decisão de alto nível. Linkar ADRs aplicáveis. Responder: qual a forma da solução?

## Data models

Classes Pydantic, schemas JSON, tabelas, formatos de arquivo. Incluir exemplos curtos.

## Contratos

Assinaturas de tools MCP, rotas HTTP, envelopes de evento. O que sai e entra em cada fronteira pública.

## Dependências

Libs novas que o bloco introduz. Para cada uma:
- Nome + versão mínima.
- Motivo.
- Alternativa considerada (se houver).

## Riscos

O que pode dar errado, e como mitigamos. Inclui risco técnico (perf, segurança) e risco de escopo.

## Estratégia de validação

Como provamos que funciona:
- Testes unitários (o quê).
- Testes de integração (o quê).
- Testes E2E (se aplicável).
- Inspeção manual (quando um teste não cobre bem).
```

### Template `tasks.md`

```markdown
---
id: NNNN-<slug>
status: todo | in_progress | done
---

## Setup

- [ ] T001 — <tarefa específica, 1 frase, executável num único commit>
- [ ] T002 — …

## Tests (TDD RED)

Um teste por AC do spec quando viável. Tarefas nesta seção **devem falhar** antes das de Implementation começarem.

- [ ] T010 — escrever teste falhando para [AC1] em `tests/…/test_x.py`
- [ ] T011 — …

## Implementation (TDD GREEN)

Código mínimo para passar cada teste. Referenciar `Txxx` da seção acima.

- [ ] T020 — implementar `<módulo>` até T010 passar
- [ ] T021 — …

## Refactor (TDD REFACTOR)

Só após tudo verde. Extrair, simplificar, remover duplicação sem mudar comportamento observável.

- [ ] T030 — extrair `<helper>` se surgir duplicação em T020/T021
- [ ] T031 — …

## Evidence

- [ ] T090 — capturar logs/screens/cov report em `docs/EVIDENCE/NNNN-<slug>.md`

## Paralelismo

Tarefas marcadas `[P]` podem ser executadas em paralelo sem conflito de arquivo. Ex.: `T010 [P]` e `T011 [P]` se tocam arquivos de teste diferentes.
```

## Estados e transições

### `spec.md`
- `draft` — em escrita, ainda com `[NEEDS CLARIFICATION]` abertos.
- `review` — escrito; aguardando resposta humana sobre ambiguidades.
- `approved` — zero ambiguidades; libera plan/tasks/checkpoint #1.
- `implemented` — após evidência aceita e docs atualizadas.
- `superseded` — substituído por spec posterior; mantido no histórico.

### `plan.md`
- `proposed` → `approved` (no checkpoint #1) → `done` (no checkpoint #2).

### `tasks.md`
- `todo` → `in_progress` (após checkpoint #1) → `done` (quando todos `[ ]` estão `[x]`).

## Rastreabilidade

Cadeia mínima para cada commit de implementação:

```
R (requisito em docs/REQUIREMENTS.md)
└── spec (docs/specs/NNNN-<slug>/spec.md, AC numerado)
    └── task (docs/specs/NNNN-<slug>/tasks.md, Txxx)
        └── test (tests/…/test_x.py::test_caso)
            └── código (módulo.py)
                └── commit (mensagem cita Txxx)
                    └── evidência (docs/EVIDENCE/NNNN-<slug>.md)
```

O `code-reviewer` recusa PRs em que algum elo da cadeia esteja faltando.

## Quem abre o quê

- **Apenas o `software-architect`** (ou o usuário) abre specs novas.
- Engenheiros de domínio implementam tasks, **não** alteram `spec.md` sem orientação. Correção de typo é tolerável; mudança de mérito exige atualização formal do spec antes do código mudar.
- `qa-engineer` escreve os testes da seção RED antes do código ser escrito.
- `code-reviewer` valida no checkpoint.

## Referências

- [ADR-0004 — SDD + TDD pragmático](../adr/0004-sdd-tdd-workflow.md)
- [ai-context/WORKFLOW.md](../../ai-context/WORKFLOW.md)
- [GitHub spec-kit](https://github.com/github/spec-kit)
- [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)
