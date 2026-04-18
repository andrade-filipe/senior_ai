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

## Robustez e guardrails

Seção obrigatória desde ADR-0008. Ordem mental: **o que o código promete (ACs) → como o código é robusto (esta seção) → como contratos semânticos amarram ao teste (Rastreabilidade DbC)**.

### Happy Path

Uma ou duas frases descrevendo a execução do caminho feliz do bloco — entrada válida típica, passos principais, saída esperada. **Sem este bloco, o engenheiro tende a implementar só o teste positivo do primeiro AC**.

### Edge cases

Tabela das situações de borda que o bloco **deve** tratar explicitamente. Cada linha com AC dedicado (P1) vira teste obrigatório em `tasks.md`. Edge cases documentados sem AC (P2) são comportamentos esperados sem teste hard-gate; ganham teste no Refactor.

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| (ex.) `image_base64` > 5 MB | rejeitar antes de decodificar | `E_OCR_IMAGE_TOO_LARGE` | `AC18` |

### Guardrails

Limites concretos que o código **deve** aplicar. Referenciam a tabela-mestre de [ADR-0008](../adr/0008-robust-validation-policy.md) / [ARCHITECTURE § Robustez e guardrails](../ARCHITECTURE.md), repetidos aqui apenas para facilitar leitura.

| Alvo | Cap / Timeout | Violação | AC ref |
|---|---|---|---|

### Security & threats

Ameaças específicas ao bloco e mitigações. Formato curto — um item por ameaça, mitigação em uma linha.

- **Ameaça**: (ex.) ReDoS em regex de CPF.
  **Mitigação**: regex ancorado + teste com input adversarial (AC19).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md`. Para cada AC que corresponde a uma pré/pós/invariante formal, listar o alvo do `plan.md § Design by Contract` e o tipo do contrato (Pre/Post/Invariant). Essa sub-seção é o elo **spec → plan** do triplo-trace que o `code-reviewer` exige; o elo **plan → tasks** vive na coluna `Task ref` da tabela DbC do `plan.md`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC4 | `pii_mask` | Post |

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

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests e AC correspondente em `spec.md § Rastreabilidade DbC`.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `nome_do_alvo` | condição que o caller garante | garantia de saída | propriedade sempre verdadeira | `AC4` | `T013 [DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` marcado `[DbC]`.
- Colunas `AC ref` e `Task ref` são **obrigatórias** — o `code-reviewer` usa o trace triplo (`AC ref` em `spec.md § Rastreabilidade DbC` + `Task ref` com tag `[DbC]` em `tasks.md` + enforcement no código) para aprovar o bloco.

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

**Convenção de tags**:
- `[P]` — paralelizável (arquivos de teste distintos, sem conflito).
- `[DbC]` — exerce uma linha da tabela DbC do `plan.md`. Acumula com `[P]` quando ambos se aplicam. O `code-reviewer` usa `[DbC]` para mecanicamente confirmar que toda linha da tabela DbC do plan tem teste correspondente em `tasks.md`; sem tag `[DbC]` onde se espera, o bloco é rejeitado.

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

## Vocabulário de patterns

Specs e ADRs podem referenciar patterns arquiteturais por nome curto quando o termo já é padrão na literatura. Glossário consolidado em [`ai-context/references/AGENTIC_PATTERNS.md § 6`](../../ai-context/references/AGENTIC_PATTERNS.md). Termos aceitos:

- **plan-then-execute** — agente produz passos antes de chamar tools (Gulli, cap. 2).
- **assembled reformat** — pipeline determinístico pós-LLM que reformata saída (Lakshmanan, cap. 3).
- **trustworthy generation with citations** — resposta do agente cita origem de cada fato (Lakshmanan, cap. 5).
- **parameter inspection** — validar argumentos de tool antes da chamada; permitir correção.
- **tool categorization (knowledge / capability / write-action)** — Huyen, cap. 6.
- **dupla camada de guardrails** — PII no OCR + `before_model_callback`; ADR-0003.
- **orchestrator-worker** — um LLM coordena sub-agentes determinísticos (Gulli, cap. 7). *Não adotado no MVP* — ver ADR-0006.

Usar o termo curto no spec e deixar o link para `AGENTIC_PATTERNS.md` fazer o trabalho de explicar.

## Referências

- [ADR-0004 — SDD + TDD pragmático](../adr/0004-sdd-tdd-workflow.md)
- [ai-context/WORKFLOW.md](../../ai-context/WORKFLOW.md)
- [ai-context/references/AGENTIC_PATTERNS.md](../../ai-context/references/AGENTIC_PATTERNS.md) — vocabulário de patterns
- [GitHub spec-kit](https://github.com/github/spec-kit)
- [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)
