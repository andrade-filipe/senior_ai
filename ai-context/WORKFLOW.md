# Fluxo de Trabalho

Este documento define o **ciclo SDD + TDD pragmático** seguido por todo bloco de trabalho. Cadência formal em [ADR-0004](../docs/adr/0004-sdd-tdd-workflow.md). Nenhum bloco pula etapas.

## Regra de ouro

> **Specs não servem ao código; o código serve às specs.**

Spec é o artefato primário; código é a expressão dela num stack específico. Quando código e spec divergem, atualizamos o spec primeiro.

## Ciclo por bloco de trabalho

```
 1. Requisito → 2. Spec → 3. Plan → 4. Tasks → [checkpoint humano #1 — COLETIVO]
                                                      ↓
 9. Checkpoint ← 8. Docs ← 7. Evidence ← 6. Review ← 5. Tests→Code
    humano #2 (por bloco)
```

Cada bloco vive em `docs/specs/NNNN-<slug>/` com três arquivos: `spec.md`, `plan.md`, `tasks.md`. Templates em [`docs/specs/README.md`](../docs/specs/README.md).

### Granularidade dos checkpoints

- **Checkpoint #1 é COLETIVO.** Passos 1–4 são executados para **todos os blocos planejados** em um único lote pelo `software-architect`. O usuário revisa o conjunto de todos os `spec+plan+tasks` de uma vez. Sem essa revisão, **nenhum teste ou código** é escrito em nenhum bloco.
- **Checkpoint #2 é POR BLOCO.** Cada bloco fecha com evidência própria e aprovação individual antes de ser marcado `done` em `STATUS.md`.

Esta granularidade habilita **paralelismo real na fase 5**: com todas as specs/tasks aprovadas, engenheiros de domínio iniciam seus blocos simultaneamente quando não há dependência de código (transpiler ↔ MCP ↔ FastAPI ↔ PII são largamente independentes; Bloco 6 depende de 3/4/5; Bloco 7 depende de todos anteriores; Bloco 8 fecha).

Formalizado em [ADR-0004 § "Granularidade do checkpoint #1"](../docs/adr/0004-sdd-tdd-workflow.md).

### 1. Requisito

**Dono:** `software-architect`.
- Identificar quais R(s) de [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) o bloco endereça.
- Se nenhum R existente se aplica — escopo está fora do desafio; parar e perguntar ao usuário.

**Saída:** lista `[Rxx, Ryy]` para o frontmatter do spec.

### 2. Spec

**Dono:** `software-architect`.
- Criar `docs/specs/NNNN-<slug>/spec.md` via template.
- Preencher: problema, user stories, critérios de aceitação (`AC1`, `AC2`…) verificáveis, requisitos não-funcionais, fora de escopo.
- Listar ambiguidades em `[NEEDS CLARIFICATION]`. Spec com itens abertos fica `status: review`.

**Saída:** `spec.md` em `status: draft | review`.

### 3. Plan

**Dono:** `software-architect`.
- Criar `plan.md` via template, **depois** que o spec está limpo (sem `[NEEDS CLARIFICATION]`).
- Definir: abordagem técnica (com links para ADRs aplicáveis), data models, contratos, dependências novas, riscos, estratégia de validação.

**Saída:** `plan.md` em `status: proposed`.

### 4. Tasks

**Dono:** `software-architect`.
- Criar `tasks.md` via template, decompondo o plan em passos executáveis.
- Seções: Setup, Tests (RED), Implementation (GREEN), Refactor, Evidence.
- Cada tarefa é 1 frase, 1 commit, com ID estável (`T001`, `T010`, `T020`…).
- Marcar `[P]` tarefas que podem rodar em paralelo (sem conflito de arquivo).

**Saída:** `tasks.md` em `status: todo`.

### Checkpoint humano #1 (coletivo)

**Dono:** o usuário.
- Apresentar **todos** os spec + plan + tasks dos blocos planejados de uma só vez.
- Sem aprovação, **nenhum teste ou código** é escrito em **nenhum** bloco.
- Retornos possíveis: "go" (libera todos), "ajustar X em bloco N" (iteração focada), "abandonar bloco N" (remove do backlog).

**Saída:** todos os specs → `approved`; todos os plans → `approved`; todos os tasks → `in_progress` (ou retornos ao passo 2/3/4 focados nos blocos com findings).

### 5. Tests → Code

Passo com três sub-fases no estilo TDD. Pragmatismo explícito:

- **Test-first obrigatório** em `transpiler/` e `security/` — código onde regressão silenciosa é cara.
- **Same-commit** (testes junto do código) em MCP servers, FastAPI e glue/infra, onde escrever teste falhando antes traz pouco sinal.

#### 5a. RED

**Dono:** `qa-engineer`.
- Escrever testes cobrindo cada AC do spec.
- Rodar: devem **falhar** — confirma que o teste é acionável.

#### 5b. GREEN

**Dono:** engenheiro de domínio do bloco (`transpiler-engineer`, `adk-mcp-engineer`, `fastapi-engineer`, `security-engineer`, `devops-engineer`).
- Escrever o código **mínimo** para os testes passarem.
- Não otimizar ainda. Não adicionar feature não pedida no spec.

#### 5c. Refactor

**Dono:** engenheiro de domínio.
- Extrair helpers, remover duplicação, melhorar nomes.
- Testes devem permanecer verdes o tempo todo.

**Saída:** código + testes verdes + cobertura ≥ 80 % nos módulos configurados.

### 6. Review

**Dono:** `code-reviewer`.
- Validar **código vs spec**, não só estilo.
- Cada AC deve ser rastreável a um teste; cada teste a uma task; cada task a uma linha de código.
- Verdict: `APPROVED` | `CHANGES REQUESTED` | `BLOCKED`.
- `CHANGES REQUESTED` → voltar a 5b/5c com findings.
- `BLOCKED` → escalar ao usuário e `software-architect` (spec pode precisar ser revisto).

**Saída:** relatório de review estruturado.

### 7. Evidence

**Dono:** `qa-engineer`.
- Rodar suíte completa + integração + (se aplicável) E2E via `docker compose up`.
- Coletar evidências em `docs/EVIDENCE/NNNN-<slug>.md`: comandos reproduzíveis, logs trimados, prints CLI/Swagger, cov report.
- Reportar cobertura dos módulos tocados.

**Saída:** arquivo de evidência + declaração `READY FOR HUMAN REVIEW`.

### 8. Docs

**Dono:** agente implementador + `software-architect`.
- Atualizar `docs/ARCHITECTURE.md` se contratos mudaram.
- Marcar `spec.md` → `status: implemented`.
- Atualizar `ai-context/STATUS.md` (bloco → `done`).
- Logar referências novas em `ai-context/LINKS.md` **no mesmo commit**.
- README final só é tocado na fase de entrega.

**Saída:** docs consistentes com o código.

### Checkpoint humano #2

**Dono:** o usuário.
- Apresentar: o que mudou, evidências, próximo bloco proposto.
- Retornos: "go" (próximo bloco) ou "review" (correções).

## Cadeia de rastreabilidade

Cada commit de implementação deve fechar:

```
R (docs/REQUIREMENTS.md)
└── spec (docs/specs/NNNN/spec.md — AC numerado)
    └── task (tasks.md — Txxx)
        └── test (tests/.../test_x.py::test_caso)
            └── código (módulo.py)
                └── commit (mensagem cita Txxx)
                    └── evidência (docs/EVIDENCE/NNNN.md)
```

`code-reviewer` recusa PRs onde algum elo está faltando.

## Ordem macro dos blocos

| # | Bloco | Agente principal | R endereçado |
|---|---|---|---|
| 1 | Schema Pydantic do spec + validação (transpilador) | transpiler-engineer | R01 |
| 2 | Transpilador MVP (Jinja2 + CLI + `ast.parse`) | transpiler-engineer | R01 |
| 3 | Servidores MCP OCR/RAG (FastMCP + SSE, mock) | adk-mcp-engineer | R02, R03, R11 |
| 4 | API FastAPI de agendamento + Swagger | fastapi-engineer | R04 |
| 5 | Camada PII (Presidio + BR recognizers) | security-engineer | R05 |
| 6 | Agente ADK end-to-end (gerado + containerizado) | adk-mcp-engineer | R06 |
| 7 | Dockerfiles + `docker-compose.yml` | devops-engineer | R07 |
| 8 | E2E + evidências + README + seção Transparência | qa-engineer + software-architect | R08, R09, R10, R12 |

## Comunicação entre agentes

- **Handoff explícito:** cada agente termina com `Hand-off to: <próximo agente>` e uma lista do que ele precisa saber.
- **Sem trabalhos paralelos conflitantes:** dois agentes nunca editam o mesmo arquivo sem coordenação do `software-architect`.
- **Zero código gerado sem `code-reviewer` antes de `qa-engineer`.**

## Quando quebrar o ciclo

Autorizado apenas para:
- Correção de typo em docs.
- Atualização isolada de `ai-context/STATUS.md` entre blocos.
- Fixes emergenciais em CI quebrado — precisam spec retroativa antes do próximo bloco.

## Layout da documentação: humanos vs IA

O repositório separa **dois públicos** de documentação. `code-reviewer` reprova PRs que misturem os dois.

### Regra de ouro

> Se o texto é **entrega** (lido pelo avaliador/reviewer humano), vai em `docs/`.
> Se o texto é **contexto operacional de trabalho** (lido por subagentes durante o desenvolvimento), vai em `ai-context/`.
> Em dúvida, opte por `docs/` — é melhor expor demais ao humano do que ocultar decisão.

### Tabela comparativa

| Aspecto | `docs/` (humano) | `ai-context/` (IA) |
|---|---|---|
| Público | Avaliador, reviewer, mantenedor futuro | Subagentes do Claude Code |
| Estilo | Narrativo, polido, estável | Operacional, denso, iterativo |
| Estabilidade | Muda só quando arquitetura/contratos mudam | Livre para evoluir a cada bloco |
| Idioma | Português (narrativa) + trechos em EN | Português + EN misturado, sem cerimônia |
| Entregáveis | Sim — parte da submissão final | Não — contexto interno, exposto por transparência |
| Imutabilidade | ADRs são imutáveis após aceite | Nada é imutável; mas `references/` deve ser verdadeiro |
| Porta de entrada | `docs/README.md` | `ai-context/README.md` |

### Mapa de conteúdo

| Conteúdo | Onde fica | Por quê |
|---|---|---|
| Transcrição do desafio | `docs/DESAFIO.md` | Fonte da verdade oficial para o avaliador. |
| Enumeração de requisitos | `docs/REQUIREMENTS.md` | IDs estáveis (R01..Rn) que os specs citam. |
| Arquitetura-alvo e contratos | `docs/ARCHITECTURE.md` | Entrega; muda só via ADR. |
| Specs, plans e tasks | `docs/specs/NNNN-<slug>/` | Artefato primário do SDD; visível ao avaliador. |
| ADRs aceitas | `docs/adr/` | Registro formal e imutável. |
| Evidências de marcos (logs/prints) | `docs/EVIDENCE/` | Prova de funcionamento para o avaliador. |
| Padrões de código/testes/segurança | `ai-context/GUIDELINES.md` | Contexto que o `code-reviewer` aplica. |
| Este fluxo de trabalho | `ai-context/WORKFLOW.md` | Processo interno; ajustável. |
| Quadro de progresso | `ai-context/STATUS.md` | Estado vivo, muda a cada checkpoint. |
| Notas técnicas de pesquisa | `ai-context/references/*.md` | Resumos para contextualizar subagentes. |
| Log de referências externas | `ai-context/LINKS.md` | Atualizado em todo commit que consumir fonte nova. |
| README final do projeto | `README.md` (raiz) | Porta de entrada humana do repositório. |
| `CLAUDE.md` | raiz | Instruções pinned para o Claude Code; aponta para ambos. |

### Casos de borda

- **Template de ADR**: mora em `docs/adr/README.md` (junto com o índice) — é entrega, não contexto interno.
- **Pesquisa exploratória em andamento**: começa como rascunho em `ai-context/references/`. Se virar decisão → ADR em `docs/adr/`.
- **Bug incidental descoberto**: registra no `ai-context/STATUS.md`. Se mudou um contrato ao corrigir → ADR + atualização em `docs/ARCHITECTURE.md`.
- **Commit misto** que toca `docs/` e `ai-context/` no mesmo PR é aceitável **apenas** quando o motivo é o mesmo (ex.: aceitar ADR e remover sua proposta das references).
