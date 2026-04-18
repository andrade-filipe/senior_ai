# ADR-0004: Workflow SDD + TDD pragmático

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

Até aqui o projeto tinha um ciclo iterativo genérico (planejar → implementar → revisar → testar → documentar). Isso garante processo mas **não garante rastreabilidade entre o que o desafio pede e o que o código entrega**, nem disciplina a geração de código por IA.

O usuário preferiu adotar **Spec-Driven Development (SDD)**, inspirado em [GitHub spec-kit](https://github.com/github/spec-kit) e no artigo [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md). Princípio central do SDD:

> *"Specifications não servem ao código; o código serve às specs."*

Além disso, o usuário adota **TDD pragmático**: test-first em módulos de alta responsabilidade (transpiler, security); testes e código no mesmo commit em glue/infra, mas nunca commit sem teste.

Este ADR formaliza o casamento SDD + TDD como processo obrigatório para todo bloco de trabalho desta entrega.

## Alternativas consideradas

1. **TDD puro, sem SDD** (estado anterior) — escreve-se o teste a partir do requisito verbal; não há spec escrita.
   - Prós: menos artefatos; velocidade alta.
   - Contras: requisito perdido entre sessões; agentes de IA não têm fonte estável para consultar; rastreabilidade requisito → código fica implícita.

2. **SDD puro, sem TDD** — spec detalhada → código, sem testes obrigatórios.
   - Prós: rastreabilidade.
   - Contras: sem gate automatizado de correção; regressões passam despercebidas.

3. **SDD + TDD pragmático (escolhido)** — o melhor dos dois: spec como fonte da verdade, TDD como gate mecânico.

4. **Adotar a CLI `spec-kit` literalmente** — instalar a ferramenta e seus slash commands.
   - Prós: reprodutível, oficial.
   - Contras: dependência externa; slash commands próprios competem com nosso fluxo com subagentes Claude Code; atrito de adoção no momento.
   - Descartado: **usamos os templates e princípios manualmente**, sem adotar a CLI.

## Decisão

Todo bloco de trabalho segue o ciclo de 9 passos abaixo, com artefatos em `docs/specs/NNNN-<slug>/`.

```
1. Requisito   →  2. Spec   →  3. Plan  →  4. Tasks  →  [checkpoint humano #1 — coletivo]
                                              ↓
9. Checkpoint  ←  8. Docs  ←  7. Evidence  ←  6. Review  ←  5a/5b/5c. Tests→Code→Refactor
humano #2
```

### Granularidade do checkpoint #1 — coletivo (não por bloco)

Quando há múltiplos blocos planejados (caso deste projeto — 8 blocos enumerados em `ai-context/WORKFLOW.md § "Ordem macro"`), os passos 1–4 são executados **para todos os blocos em um único lote** e o checkpoint humano #1 é **coletivo**: o usuário revisa o conjunto de `spec+plan+tasks` de todos os blocos de uma vez.

Justificativas:

- **Paralelismo na fase 5.** Com todas as specs/tasks aprovadas, os engenheiros de domínio (`transpiler-engineer`, `adk-mcp-engineer`, `fastapi-engineer`, `security-engineer`, `devops-engineer`) podem iniciar seus blocos **simultaneamente** quando não há dependência de código entre eles. Checkpoint por bloco serializaria o caminho crítico sem ganho.
- **Coerência cross-bloco detectada cedo.** A revisão humana vê, num único passe, se contratos descritos em diferentes specs batem (ex.: tool signatures no Bloco 3 vs import no Bloco 6).
- **Custo cognitivo concentrado.** Ao invés de 8 checkpoints pequenos, um checkpoint maior mas único.

O **checkpoint #2** permanece **por bloco** — cada bloco entrega evidências próprias; o usuário valida antes de marcar como `done`.

O passo 2 (Spec) é escrito com base em ADRs e `docs/ARCHITECTURE.md` já frozen, o que reduz o risco de incoerência entre specs geradas em lote.

### Passos

| # | Passo | Dono | Entregável |
|---|---|---|---|
| 1 | **Requisito** | software-architect | Identificar R(s) em `docs/REQUIREMENTS.md` que o bloco endereça. |
| 2 | **Spec** | software-architect | `docs/specs/NNNN/spec.md` — problema, user stories, critérios de aceitação verificáveis, `[NEEDS CLARIFICATION]` para ambiguidades. |
| 3 | **Plan** | software-architect | `docs/specs/NNNN/plan.md` — abordagem técnica, data models, contratos, riscos, estratégia de validação. |
| 4 | **Tasks** | software-architect | `docs/specs/NNNN/tasks.md` — lista granular numerada (T001…) em seções Setup / Tests RED / Impl GREEN / Refactor / Evidence; marca `[P]` para tasks paralelizáveis. |
| — | **Checkpoint humano #1** | usuário | Aprovar spec+plan+tasks. Sem aprovação, nenhum teste ou código é escrito. |
| 5a | **Tests (RED)** | qa-engineer | Testes falhos cobrindo cada AC do spec; rodar e confirmar falha. |
| 5b | **Code (GREEN)** | engenheiro de domínio | Código mínimo para passar os testes do passo 5a. |
| 5c | **Refactor** | engenheiro de domínio | Limpeza mantendo testes verdes. |
| 6 | **Review** | code-reviewer | Validação **código vs spec** (não apenas estilo). Verdict: APPROVED / CHANGES / BLOCKED. |
| 7 | **Evidence** | qa-engineer | `docs/EVIDENCE/NNNN.md` com logs, cov report, prints CLI/Swagger. |
| 8 | **Docs** | software-architect + implementador | ARCHITECTURE/STATUS atualizados; LINKS.md com fontes novas; spec → `status: implemented`. |
| 9 | **Checkpoint humano #2** | usuário | "go" próximo bloco ou "review" correções. |

### Regra de TDD pragmático

- **Test-first obrigatório** em `transpiler/` e `security/` (gate de cobertura ≥ 80 %).
- **Testes e código no mesmo commit** em `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, `generated_agent/`, infra. Ordem livre, mas PR sem teste correspondente não merge.
- Refactor **só** com todos os testes verdes.

### Regra de ouro

Quando código e spec divergirem, **atualizamos a spec primeiro**, depois o código. A spec é o artefato fonte; ADR nova supersede decisão se a mudança for arquitetural.

### Templates

Os 3 templates (spec/plan/tasks) ficam em `docs/specs/README.md` e são copiados para cada novo bloco.

## Consequências

- **Positivas**: rastreabilidade requisito → spec → teste → código; subagentes têm contexto estável (a spec) entre sessões; `code-reviewer` tem critério objetivo para revisar (o spec); avaliador humano vê o processo em `docs/specs/`.
- **Negativas**: 3 arquivos extras por bloco; ciclo inicial mais lento (compensado pela clareza nos ciclos seguintes); requer disciplina de não pular o checkpoint #1.
- **Impacto**: todo o `ai-context/WORKFLOW.md` é reescrito com este ciclo; cada agente ganha "Papel no ciclo SDD+TDD" no seu prompt; `ai-context/STATUS.md` passa a listar blocos por NNNN-slug.

## Referências

- `docs/specs/README.md` — templates SDD
- `docs/REQUIREMENTS.md` — enumeração R01..Rn
- `ai-context/WORKFLOW.md` — ciclo detalhado
- https://github.com/github/spec-kit
- https://github.com/github/spec-kit/blob/main/spec-driven.md
- https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

> Editado em 2026-04-18 durante fase pré-implementação: checkpoint humano #1 passa a ser **coletivo** (um único passe sobre spec+plan+tasks de todos os blocos planejados), em vez de por bloco. Motivação registrada em seção "Granularidade do checkpoint #1". Mudança de processo, não de método — SDD + TDD pragmático permanecem. Checkpoint #2 continua por bloco.
