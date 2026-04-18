# Instruções para o Assistente

Este projeto é o **Desafio Técnico Sênior IA** — transpilador JSON → ADK + MCP-SSE + FastAPI + PII Guard + Docker.

## Layout do repositório (essencial)

```
CLAUDE.md                     # este arquivo (pinned para o Claude Code)
.claude/agents/               # 8 subagentes especializados
ai-context/                   # contexto de trabalho da IA (NÃO é entrega)
├── GUIDELINES.md             # padrões operacionais (código, testes, segurança, git)
├── WORKFLOW.md               # ciclo SDD+TDD + regra humano-vs-IA
├── STATUS.md                 # quadro vivo de progresso
├── LINKS.md                  # log de fontes externas consultadas
└── references/               # notas técnicas consolidadas
docs/                         # entrega humana (parte da submissão)
├── DESAFIO.md                # transcrição do PDF do desafio
├── REQUIREMENTS.md           # R01..Rn — IDs estáveis referenciados pelos specs
├── ARCHITECTURE.md           # arquitetura oficial + contratos
├── EVIDENCE/                 # logs/prints por marco
├── adr/                      # ADRs aceitas (imutáveis)
└── specs/                    # artefato primário do SDD (NNNN-slug/ com spec+plan+tasks)
```

## Leituras obrigatórias antes de propor qualquer mudança

1. `docs/DESAFIO.md` — fonte da verdade sobre o que construir.
2. `docs/REQUIREMENTS.md` — R01..Rn com IDs estáveis; cada spec cita os R(s) que endereça.
3. `docs/ARCHITECTURE.md` — arquitetura-alvo e contratos entre serviços.
4. `docs/adr/` — decisões arquiteturais aceitas (7 ADRs; índice em `docs/adr/README.md`).
5. `docs/specs/README.md` — método SDD adotado e templates (`spec.md`, `plan.md`, `tasks.md`).
6. `ai-context/GUIDELINES.md` — padrões de código, segurança, testes, docs.
7. `ai-context/WORKFLOW.md` — ciclo SDD + TDD de 9 passos.
8. `ai-context/STATUS.md` — estado atual dos blocos.

## Subagentes disponíveis (`.claude/agents/`)

| Agente | Use para |
|---|---|
| `software-architect` | Planejamento, decomposição, ADRs, contratos. |
| `transpiler-engineer` | Transpilador JSON→ADK (schema, templates, CLI). |
| `adk-mcp-engineer` | Servidores MCP-SSE e agente ADK consumidor. |
| `fastapi-engineer` | API FastAPI de agendamento. |
| `security-engineer` | Camada PII (Presidio + BR recognizers). |
| `devops-engineer` | Dockerfiles, docker-compose, healthchecks. |
| `qa-engineer` | Testes, cobertura, evidências. |
| `code-reviewer` | Revisão independente antes de cada marco. |

Sempre que possível, delegue ao subagente correto em vez de implementar direto.

## Regra humano-vs-IA para documentação

- **É entrega para humano** (avaliador, reviewer): vai em `docs/`. Estilo narrativo, em português, estável.
- **É contexto de trabalho da IA**: vai em `ai-context/`. Estilo operacional, livre para mudar a cada iteração.
- Em dúvida: abra para o humano (use `docs/`).

Detalhes e exemplos em `ai-context/WORKFLOW.md` (seção "Layout da documentação").

## Princípios não-negociáveis

- **SDD + TDD pragmático** como método obrigatório (fixado em ADR-0004): spec → plan → tasks → checkpoint #1 → RED → GREEN → review → evidence → checkpoint #2. Nenhum teste ou código é escrito antes do checkpoint #1. Test-first é obrigatório em `transpiler/` e `security/`; same-commit nos demais módulos.
- **Stack fechada** (ADR-0005): `uv` + Gemini direct API (`gemini-2.5-flash`) + GitHub Actions mínimo. Mudança em qualquer item exige ADR nova supersedendo.
- **Nenhum código** é aceito sem `code-reviewer` + aprovação humana.
- **PII mascarada antes** de qualquer LLM ou persistência — dupla camada (ADR-0003).
- **MCP transport = SSE**, exigência do desafio (ADR-0001).
- **README/docs em PT; código/commits em EN**.
- **Conventional Commits** em inglês; commits pequenos. Commits de implementação citam `Txxx` (task) ou `ACn` (critério de aceitação) do spec.
- **`.env` nunca no git**. `.env.example` sim.

## Fluxo de trabalho resumido

```
Requisito → Spec → Plan → Tasks → [checkpoint #1]
                                       ↓
[checkpoint #2] ← Docs ← Evidence ← Review ← RED → GREEN → Refactor
```

Detalhes (donos, entregáveis por passo) em `ai-context/WORKFLOW.md`.

## Arquivos que não devem ser tocados sem coordenação

- `docs/adr/*.md` — imutáveis após aceite (só `software-architect` abre novos).
- `CLAUDE.md` — este arquivo; só atualizar para refletir mudança de processo.

## Contato

Dúvida sobre escopo ou prioridade → perguntar ao usuário antes de avançar.
