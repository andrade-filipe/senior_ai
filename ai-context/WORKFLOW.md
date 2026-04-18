# Fluxo de Trabalho

Este documento define o **ciclo iterativo** seguido até a entrega final. Todo bloco de trabalho passa pelos 7 passos abaixo; nenhum bloco pula etapas.

## Ciclo por bloco de trabalho

```
1. Especificar  →  2. Planejar  →  3. Implementar  →  4. Revisar
                                         ▲                │
                                         │                ▼
                               7. Checkpoint humano  ←  5. Testar  →  6. Documentar
```

### 1. Especificar
**Dono:** `software-architect`.
- Ler `docs/DESAFIO.md`, `docs/ARCHITECTURE.md`, `ai-context/STATUS.md`.
- Delimitar o bloco: *qual parte do sistema*, *contratos afetados*, *critérios de aceitação* mensuráveis.
- Se há mudança de contrato público entre subsistemas → abrir ADR (`docs/adr/NNNN-*.md`).
- Atualizar `ai-context/STATUS.md` adicionando o bloco como `planned`.

**Saída:** uma entrada no STATUS + (opcional) ADR.

### 2. Planejar
**Dono:** `software-architect`.
- Decompor em passos executáveis; cada passo tem arquivo(s) alvo, agente responsável e critério de "pronto".
- Em blocos grandes (> ~3 passos de implementação), usar `EnterPlanMode` e obter aprovação do usuário.
- Em blocos pequenos, documentar o plano no próprio commit / entrada do STATUS.

**Saída:** lista de passos atribuídos a agentes de engenharia.

### 3. Implementar
**Dono:** agente de domínio (`transpiler-engineer`, `adk-mcp-engineer`, `fastapi-engineer`, `security-engineer`, `devops-engineer`).
- Escrever código + testes unitários **no mesmo commit**.
- Respeitar o escopo declarado no prompt do agente (sem cruzar fronteiras).
- Atualizar notas técnicas (`ai-context/references/*.md`) quando aprender algo novo.
- Toda fonte externa consultada (doc oficial, blog, RFC) entra em `ai-context/LINKS.md` **no mesmo commit**. Sem rastreabilidade, não merge.

**Saída:** diff com código + testes + atualizações de referência.

### 4. Revisar
**Dono:** `code-reviewer`.
- Rodar sempre, antes do teste integrado.
- Verdict: `APPROVED` | `CHANGES REQUESTED` | `BLOCKED`.
- Se `CHANGES REQUESTED` → voltar ao passo 3 com findings anexados.
- Se `BLOCKED` → escalar para o usuário + `software-architect` (possível revisão de plano).

**Saída:** relatório de review estruturado.

### 5. Testar
**Dono:** `qa-engineer`.
- Rodar suíte completa afetada pelo bloco.
- Para marcos principais: executar teste E2E via `docker compose up`.
- Coletar evidências (logs trimados, prints CLI/Swagger) em `docs/EVIDENCE/<bloco>.md`.
- Reportar cobertura dos módulos tocados.

**Saída:** relatório com comandos reproduzíveis + evidências; declarar `READY FOR HUMAN REVIEW` quando tudo passar.

### 6. Documentar
**Dono:** agente implementador + `software-architect`.
- Atualizar `docs/ARCHITECTURE.md` se contratos mudaram.
- Atualizar `ai-context/STATUS.md` marcando o bloco como `done`.
- README final só é tocado na última fase (entrega).

**Saída:** docs atualizados e consistentes com o código.

### 7. Checkpoint humano
**Dono:** o usuário.
- Apresentar ao usuário: *o que mudou*, *evidências*, *próximo bloco proposto*.
- Esperar aprovação antes de abrir o próximo ciclo.

**Saída:** "go" (próximo bloco) ou "review" (correções).

## Ordem macro dos blocos

| # | Bloco | Agente principal |
|---|---|---|
| 1 | JSON schema + Pydantic do transpilador | transpiler-engineer |
| 2 | Transpilador MVP (Jinja2 + generator + CLI) | transpiler-engineer |
| 3 | Servidores MCP OCR/RAG (FastMCP + SSE, mock) | adk-mcp-engineer |
| 4 | API FastAPI de agendamento + Swagger | fastapi-engineer |
| 5 | Camada PII (Presidio + BR recognizers) | security-engineer |
| 6 | Agente ADK end-to-end (gerado + containerizado) | adk-mcp-engineer |
| 7 | Dockerfiles + docker-compose.yml | devops-engineer |
| 8 | Testes E2E + evidências + README + ADRs finais | qa-engineer + software-architect |

## Comunicação entre agentes
- **Handoff explícito:** cada agente termina com `Hand-off to: <próximo agente>` e uma lista do que ele precisa saber.
- **Sem trabalhos paralelos conflitantes:** dois agentes nunca editam o mesmo arquivo sem coordenação do `software-architect`.
- **Zero código gerado sem `code-reviewer` antes de `qa-engineer`.**

## Quando quebrar o ciclo
Autorizado apenas para:
- Bug crítico detectado em produção (neste caso, não há — sempre completar o ciclo).
- Correção de typo em docs.
- Atualização de `ai-context/STATUS.md` isolada.

## Layout da documentação: humanos vs IA

O repositório separa **dois públicos** de documentação. A regra é estrita e o `code-reviewer` reprova PRs que misturem os dois.

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
| Arquitetura-alvo e contratos | `docs/ARCHITECTURE.md` | Entrega; muda só via ADR. |
| ADRs aceitas | `docs/adr/` | Registro formal e imutável. |
| Evidências de marcos (logs/prints) | `docs/EVIDENCE/` | Prova de funcionamento para o avaliador. |
| Padrões de código/testes/segurança | `ai-context/GUIDELINES.md` | Contexto que o `code-reviewer` aplica. |
| Este fluxo de trabalho | `ai-context/WORKFLOW.md` | Processo interno; ajustável. |
| Quadro de progresso | `ai-context/STATUS.md` | Estado vivo, muda a cada checkpoint. |
| Notas técnicas de pesquisa | `ai-context/references/*.md` | Resumos para contextualizar subagentes. |
| README final do projeto | `README.md` (raiz) | Porta de entrada humana do repositório. |
| `CLAUDE.md` | raiz | Instruções pinned para o Claude Code; aponta para ambos. |

### Casos de borda

- **Template de ADR**: mora em `docs/adr/README.md` (junto com o índice) — é entrega, não contexto interno.
- **Pesquisa exploratória em andamento**: começa como rascunho em `ai-context/references/`. Se virar decisão → ADR em `docs/adr/`.
- **Bug incidental descoberto**: registra no `ai-context/STATUS.md`. Se mudou um contrato ao corrigir → ADR + atualização em `docs/ARCHITECTURE.md`.
- **Commit misto** que toca `docs/` e `ai-context/` no mesmo PR é aceitável **apenas** quando o motivo é o mesmo (ex.: aceitar ADR e remover sua proposta das references).
