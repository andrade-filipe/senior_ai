# Instruções para o Assistente

Este projeto é o **Desafio Técnico Sênior IA** — transpilador JSON → ADK + MCP-SSE + FastAPI + PII Guard + Docker.

## Layout do repositório (essencial)

```
CLAUDE.md                     # este arquivo (pinned para o Claude Code)
.claude/agents/               # 8 subagentes especializados
ai-context/                   # contexto de trabalho da IA (NÃO é entrega)
├── GUIDELINES.md             # padrões operacionais (código, testes, segurança, git)
├── WORKFLOW.md               # ciclo iterativo + regra humano-vs-IA
├── STATUS.md                 # quadro vivo de progresso
└── references/               # notas técnicas consolidadas
docs/                         # entrega humana (parte da submissão)
├── DESAFIO.md                # transcrição do PDF do desafio
├── ARCHITECTURE.md           # arquitetura oficial + contratos
├── EVIDENCE/                 # logs/prints por marco
└── adr/                      # ADRs aceitas (imutáveis)
```

## Leituras obrigatórias antes de propor qualquer mudança

1. `docs/DESAFIO.md` — fonte da verdade sobre o que construir.
2. `docs/ARCHITECTURE.md` — arquitetura-alvo e contratos entre serviços.
3. `ai-context/GUIDELINES.md` — padrões de código, segurança, testes, docs.
4. `ai-context/WORKFLOW.md` — ciclo iterativo que seguimos.
5. `ai-context/STATUS.md` — estado atual dos blocos.

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

- **Nenhum código** é aceito sem `code-reviewer` + aprovação humana.
- **PII mascarada antes** de qualquer LLM ou persistência.
- **MCP transport = SSE**, exigência do desafio.
- **README/docs em PT; código/commits em EN**.
- **Conventional Commits** em inglês; commits pequenos.
- **`.env` nunca no git**. `.env.example` sim.

## Fluxo de trabalho resumido

```
Especificar → Planejar → Implementar → Revisar → Testar → Documentar → Checkpoint humano
```

Detalhes em `ai-context/WORKFLOW.md`.

## Arquivos que não devem ser tocados sem coordenação

- `docs/adr/*.md` — imutáveis após aceite (só `software-architect` abre novos).
- `CLAUDE.md` — este arquivo; só atualizar para refletir mudança de processo.

## Contato

Dúvida sobre escopo ou prioridade → perguntar ao usuário antes de avançar.
