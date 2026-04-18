# STATUS — Quadro Vivo

Atualizado a cada checkpoint humano. `software-architect` escreve; outros agentes leem.

## Legenda

- `planned` — bloco definido, ainda não iniciado.
- `ready` — pré-requisitos atendidos; pronto para iniciar no próximo kickoff.
- `in_progress` — em implementação.
- `review` — aguardando `code-reviewer`.
- `testing` — em `qa-engineer`.
- `done` — aprovado pelo usuário.
- `blocked` — travado; ver "Impedimentos".

## Fase atual: **Implementação — Onda 1 concluída**

Próxima fase: **Onda 2 (Blocos 0002 Transpiler MVP + 0005 PII Guard em paralelo)**.

## Quadro de blocos

| Bloco | Status | Dono | R(s) | Notas |
|---|---|---|---|---|
| 0. Preparação — docs, agentes, guidelines | `done` | software-architect | — | Concluída em 2026-04-18 (commit `eca4bdf`). |
| 0.5. Design Técnico — 7 ADRs, requisitos, templates SDD, concretizações | `done` | software-architect | — | Concluída em 2026-04-18. |
| 1. Schema `AgentSpec` Pydantic + validação (transpilador) | `done` | transpiler-engineer | R01 | Concluída em 2026-04-18. 13 testes verdes; cobertura 97.73 %; `mypy --strict` limpo. Evidência em `docs/EVIDENCE/0001-agentspec-schema.md`. |
| 2. Transpilador MVP (Jinja2 + generator + CLI) | `ready` | transpiler-engineer | R01 | Pré-requisito (1) atendido. Usa ADR-0002 (Jinja2 + `ast.parse`). AC13 (CLI stderr canonical shape) adotado deste bloco. |
| 3. Servidores MCP OCR/RAG (mock, SSE) | `planned` | adk-mcp-engineer | R02, R03, R11 | ADR-0001 (SSE) + ADR-0007 (rapidfuzz + CSV). |
| 4. API FastAPI de agendamento + Swagger | `planned` | fastapi-engineer | R04 | Contrato em `docs/ARCHITECTURE.md`. |
| 5. Camada PII (Presidio + BR recognizers) | `planned` | security-engineer | R05 | ADR-0003 (dupla camada). Test-first obrigatório. |
| 6. Agente ADK end-to-end | `planned` | adk-mcp-engineer | R06 | ADR-0006 (LlmAgent único). Consome (3), (4), (5). Instruction deve incorporar backlog de patterns em `ai-context/references/AGENTIC_PATTERNS.md § 2` (plan-then-execute, parameter inspection, trustworthy citations, retry/fallback). |
| 7. Dockerfiles + `docker-compose.yml` | `planned` | devops-engineer | R07 | `uv pip install --system` (ADR-0005). |
| 8. E2E + evidências + README + Transparência | `planned` | qa-engineer + software-architect | R08, R09, R10, R12 | Última fase; fecha o desafio. |

## Impedimentos

*(nenhum no momento)*

## Histórico de checkpoints

- **2026-04-18** — Preparação concluída (commit `eca4bdf`): 8 subagentes, separação `docs/` vs `ai-context/`, WORKFLOW, GUIDELINES, ARCHITECTURE (esqueleto), CLAUDE.md, `.gitignore`, git init + remote.
- **2026-04-18** — Design Técnico concluída (commit `3c35ad2`): 7 ADRs aceitas; `docs/REQUIREMENTS.md` com R01..R12; `docs/specs/README.md` com templates SDD; `docs/ARCHITECTURE.md` com schema Pydantic + tool signatures + PII entities + error taxonomy + log format; `ai-context/WORKFLOW.md` com ciclo SDD+TDD de 9 passos; 8 agentes anotados com ADRs aplicáveis + papel no ciclo; `CLAUDE.md` com stack fechada.
- **2026-04-18** — Auditoria crítica do design (laudo em `ai-context/references/DESIGN_AUDIT.md`): 10 claims externos + 7 checagens internas + 5 riscos. Correções factuais aplicadas inline: Gemini `2.0-flash` → `2.5-flash` (descontinuado); `MCPToolset(SseConnectionParams)` → `McpToolset(StreamableHTTPConnectionParams)` (ADK renomeou); Presidio BR recognizers documentados como custom (lib não oferece); URL docs ADK migrada para `adk.dev/`. Nenhuma mudança de mérito → zero ADR nova.
- **2026-04-18** — Hardening pass (ADR-0008 "Robustez de validação"): política centralizada de taxonomia de erros `E_*`, shape canônico `{code, message, hint, path, context}`, guardrails (caps de listas/strings/bytes, timeouts), correlation_id, regra "no-PII-in-logs". 20 novos ACs (P1) distribuídos entre os 8 blocos, com ~34 novos tests `[DbC]` em `tasks.md`. Extensões em `docs/ARCHITECTURE.md` (seção "Robustez e guardrails" com tabela consolidada de códigos + guardrails + timeouts), `docs/specs/README.md` (template extendido), `.claude/agents/code-reviewer.md` (checklist ADR-0008) e `ai-context/GUIDELINES.md` (pointers). Pendente: kickoff do Bloco 1 (aguarda autorização do usuário).
- **2026-04-18** — Onda 1 concluída (Bloco 0001 — AgentSpec Schema): `transpiler/` pacote inaugurado, 13 testes unitários cobrindo AC1–AC13 (AC13 parcial — CLI test diferido ao Bloco 0002), cobertura 97.73 %, `mypy --strict` limpo. `code-reviewer` (Opus) aprovou com ressalvas menores — todas as 11 tratadas (5 fixes aplicados, 6 já cobertas pelo primeiro pass). Ambiente: `uv 0.11.7` + Python 3.12.13 gerenciado via `uv python install`. Dev deps migradas de `[project.optional-dependencies]` para `[dependency-groups]` (PEP 735) para que `uv sync` instale tudo por default. Evidência: `docs/EVIDENCE/0001-agentspec-schema.md`.
