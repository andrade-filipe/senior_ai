# STATUS — Quadro Vivo

Atualizado a cada checkpoint humano. `software-architect` escreve; outros agentes leem.

## Legenda
- `planned` — bloco definido, ainda não iniciado.
- `in_progress` — em implementação.
- `review` — aguardando `code-reviewer`.
- `testing` — em `qa-engineer`.
- `ready` — pronto para revisão humana.
- `done` — aprovado pelo usuário.
- `blocked` — travado; ver "Impedimentos".

## Fase atual: **Preparação**

| Bloco | Status | Dono | Notas |
|---|---|---|---|
| 0. Preparação — docs, agentes, guidelines | `done` | software-architect | Concluída em 2026-04-18. |
| 1. Schema JSON + Pydantic do transpilador | `planned` | transpiler-engineer | Aguarda kickoff da fase de implementação. |
| 2. Transpilador MVP (Jinja2 + generator + CLI) | `planned` | transpiler-engineer | Depende de (1). |
| 3. Servidores MCP OCR/RAG (mock, SSE) | `planned` | adk-mcp-engineer | — |
| 4. API FastAPI de agendamento + Swagger | `planned` | fastapi-engineer | — |
| 5. Camada PII (Presidio + BR recognizers) | `planned` | security-engineer | Integra em (3) e no agente. |
| 6. Agente ADK end-to-end | `planned` | adk-mcp-engineer | Consome (3), (4), (5). |
| 7. Dockerfiles + docker-compose.yml | `planned` | devops-engineer | — |
| 8. Testes E2E + evidências + README + ADRs finais | `planned` | qa-engineer + software-architect | — |

## Impedimentos
*(nenhum no momento)*

## Histórico de checkpoints
- **2026-04-18** — Preparação concluída: 8 subagentes, 6 docs de processo, CLAUDE.md, .gitignore, git init. Pendente: usuário informar a técnica de desenvolvimento (TDD/BDD/outra) para iniciar Bloco 1.
