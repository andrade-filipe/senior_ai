# Agentic Design Patterns — contexto consolidado

- **Data da consolidação**: 2026-04-18 (pós-auditoria de design, pré-Bloco 1).
- **Objetivo**: capturar o vocabulário e os padrões aprendidos na pesquisa externa sobre agentes de IA, mapeando cada um ao nosso projeto. Documento é **AI context** (não entrega ao avaliador) — todos os agentes deste repo podem referenciar padrões deste arquivo em specs, planos e ADRs.
- **Fontes primárias**:
  - Gulli, Antonio — *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (Springer, 2025). 21 capítulos + 7 apêndices. Doc público parcial no Google Docs.
  - Huyen, Chip — *AI Engineering: Building Applications with Foundation Models* (O'Reilly, 2025). Blog posts complementares sobre Agents e GenAI Platform.
  - Lakshmanan, V. & Hapke, H. — *Generative AI Design Patterns* (O'Reilly, 2025). 32 padrões organizados em 6 grupos.
  - Ng, Andrew — tweet-manifesto sobre os 4 padrões agentic (Reflection, Tool Use, Planning, Multi-Agent).

URLs completas em `ai-context/LINKS.md` § Agentic Patterns.

---

## 1. Patterns adotados no software que estamos construindo

Lista do que o design atual **já implementa**, com pointer ao arquivo/seção responsável. Serve como check mental antes de propor mudanças — se o padrão já existe, não reinvente.

| Pattern | Fonte | Onde no nosso design |
|---|---|---|
| **MCP** (Model Context Protocol) | Gulli Ch — MCP; exigência do DESAFIO | [ADR-0001](../../docs/adr/0001-mcp-transport-sse.md) — transporte SSE. |
| **Tool Use** (knowledge + write action) | Huyen — *Agents*; Gulli Ch 5; Lakshmanan #21 | `docs/ARCHITECTURE.md` seção "Serviços" + "Classificação das tools". |
| **Guardrails** (pré-LLM + pós-retorno de tool) | Gulli Ch 18; Lakshmanan #32; Huyen — *GenAI Platform* | [ADR-0003](../../docs/adr/0003-pii-double-layer.md) — dupla camada. |
| **Basic RAG** | Lakshmanan #6; Gulli Ch — Knowledge Retrieval | [ADR-0007](../../docs/adr/0007-rag-fuzzy-and-catalog.md) — rapidfuzz + CSV. |
| **Dependency Injection** (swap OCR real↔mock) | Lakshmanan #19 | R11 (mock determinístico) — `docs/REQUIREMENTS.md`. |
| **Reflection** (generate→critique→refine) | Ng; Gulli Ch 4; Lakshmanan #18 | `.claude/agents/code-reviewer.md` — papel explícito no ciclo SDD+TDD. |
| **Multi-Agent / Orchestrator-Worker** | Gulli Ch 7; Ng; SitePoint 2026 guide | Nossa topologia de 8 subagentes com `software-architect` como orquestrador (`CLAUDE.md`, `.claude/agents/`). |
| **Human-in-the-Loop** (checkpoints) | Gulli Ch — HITL | [ADR-0004](../../docs/adr/0004-sdd-tdd-workflow.md) — checkpoints #1 e #2 do ciclo SDD+TDD. |
| **Observabilidade** (correlation_id + logs estruturados) | Huyen — *GenAI Platform* layer 6 | `docs/ARCHITECTURE.md` § "Formato de log". |
| **Dead-letter / error taxonomy** | Gulli Ch 12 (Exception Handling) | `docs/ARCHITECTURE.md` § "Taxonomia de erros". |

## 2. Patterns aplicáveis ao **agente que vamos gerar** (Bloco 6 — backlog de decisão)

Estes patterns **não estão aplicados ainda**. Servem de material para quando o `spec.md` do Bloco 6 (agente ADK end-to-end) for aberto. A `instruction` do `spec.example.json` deve incorporá-los.

### 2.1. Plan-then-Execute (Huyen; Gulli Ch 6)

**Problema:** agentes que executam tool calls reativamente gastam tokens e fazem passos redundantes.
**Aplicação:** a `instruction` do agente orienta explicitamente o fluxo em 3 fases:
1. **Plan**: ler a imagem, extrair lista completa de exames (1 call ao OCR).
2. **Fetch**: para cada exame, buscar código via RAG — idealmente em paralelo.
3. **Act**: fazer UM POST agregado à scheduling-api (não um POST por exame).

Isso vira um AC do Bloco 6: "o agente fecha o fluxo em ≤5 tool calls para até 10 exames".

### 2.2. Parallelization de tool calls (Gulli Ch 3; Huyen)

**Problema:** se OCR retorna N exames e o agente chama `search_exam_code` serialmente, latência = N × call_latency.
**Aplicação:** estimular o Gemini a emitir múltiplas tool calls na mesma resposta (function calling suporta isso). A `instruction` deve dizer: *"chame search_exam_code para todos os exames em paralelo, não em sequência"*.
**Risco:** ADK pode serializar internamente dependendo da versão; medir em E2E.

### 2.3. Assembled Reformat (Lakshmanan #30)

**Problema:** se o agente formata o output final enquanto ainda está buscando dados, ele alucina códigos que ainda não chegaram.
**Aplicação:** separar em dois passos explícitos na `instruction`:
1. "Monte uma lista interna estruturada `[(nome, código, score, id_agendamento)]`."
2. "**Só depois** formate a tabela final que vai para o terminal."

### 2.4. Trustworthy Generation com citations (Lakshmanan #11)

**Problema:** output "Hemograma → HMG-001" sem rastreio é indistinguível de alucinação.
**Aplicação:** output final cita origem + score:
```
Hemograma Completo → HMG-001 (rag-mcp, score 0.98, correlation_id=c-abc123)
```
O score serve de gate: se <0.80 (threshold RAG), marcar como "não-conclusivo" em vez de reportar como match.

### 2.5. Parameter Inspection (Huyen)

**Problema:** function calls com parâmetros errados silenciosamente produzem resultados ruins.
**Aplicação:** `logging.info("tool.called", extra={"tool": name, "params_hash": sha256_prefix(params)})`. Já temos o formato de log — basta prescrever a convenção no template do agente.

### 2.6. Exception Handling / Retry (Gulli Ch 12)

**Problema:** `E_MCP_TIMEOUT`, `E_RAG_NO_MATCH`, `E_API_VALIDATION` hoje só propagam.
**Aplicação:** na `instruction` do agente, definir política:
- Timeout → 1 retry com backoff 500ms.
- `E_RAG_NO_MATCH` → cair no `list_exams` top-5 e perguntar ao usuário (degraded mode).
- `E_API_VALIDATION` → não tentar de novo; reportar ao usuário.

**Status:** registrar como `[NEEDS CLARIFICATION]` no `spec.md` do Bloco 6 para o usuário confirmar a política.

## 3. Patterns aplicáveis aos **nossos subagentes** (os agents Claude Code)

Aqui patterns orientam como o Claude Code orquestra os 8 agentes especializados durante a implementação. Estas observações **não** são código — são lentes para interpretar o que já está em `.claude/agents/*.md`.

| Pattern | Leitura do nosso setup |
|---|---|
| **Reflection** | `code-reviewer` = critique agent. Runs depois de GREEN e antes de Evidence. Seu veredict pode forçar revisão (iteration). Já é uma reflection loop explícita. |
| **LLM-as-Judge** (Lakshmanan #17) | Poderíamos usar `qa-engineer` para julgar o texto gerado pelo agente (ex.: "o output final cita corretamente as origens?"). **Aplicar só se** testes determinísticos não bastarem — evitar custo desnecessário. |
| **Human-in-the-Loop** | Nossos 2 checkpoints (#1 antes de RED, #2 depois de Evidence) são exatamente o pattern. Estão em `ai-context/WORKFLOW.md`. |
| **Orchestrator-Worker** | `software-architect` = orquestrador. Engenheiros de domínio = workers. `CLAUDE.md` mapeia responsabilidades. |
| **Inter-Agent Communication (A2A)** | Nossos agentes não conversam diretamente — conversam via artefatos (spec, plan, tasks, status). Padrão "shared state" mais simples que A2A e suficiente para o escopo. |

**Ação concreta pequena**: o `code-reviewer.md` hoje descreve seu papel sem citar "reflection pattern". Futura melhoria de baixo custo: adicionar uma linha mencionando-o — torna o comportamento esperado mais explícito para o Claude Code. Não aplicado agora (muda subagente); fica como observação.

## 4. Patterns conscientemente **não adotados** (documentar a escolha)

Para evitar que alguém no futuro pergunte "por que não usamos X?", registro aqui o que rejeitamos e por quê. Se o contexto mudar, abre-se ADR nova.

| Pattern | Fonte | Por que rejeitado |
|---|---|---|
| **Router / Gateway de modelos** | Huyen — *GenAI Platform* L3 | 1 modelo (`gemini-2.5-flash`), 1 agente. Router vira overhead sem ganho. |
| **Cache semântico** | Huyen L4; Lakshmanan #25 | Fluxo é single-shot por imagem; não há repetição de queries. Cache vira complexidade inútil no escopo MVP. |
| **Tree of Thoughts** | Lakshmanan #14 | Fluxo é determinístico (OCR → RAG → API). Não há "escolha entre múltiplos caminhos de raciocínio" — seria overkill. |
| **Long-Term Memory** | Lakshmanan #28; Gulli Ch — Memory | Agente é stateless por imagem. Session state do ADK (`InMemorySessionService`) é o bastante. |
| **Fine-tuning / Adapter Tuning** | Lakshmanan #15 | Zero custo de fine-tune no escopo; `gemini-2.5-flash` base atende. |
| **Self-Check via logit distribution** | Lakshmanan #31 | Requer acesso a logits; Gemini API não expõe com a granularidade necessária. |
| **Reasoning Techniques profundas (CoT explícito)** | Lakshmanan #13; Gulli Ch 17 | `gemini-2.5-flash` já faz reasoning interno satisfatório para o escopo. CoT só valeria a pena se tivéssemos fluxo com múltiplas decisões condicionais. |
| **Tool Use pesado (>13 tools)** | Huyen | Estamos em **3 tools**. Sem risco de tool-overload. Observação apenas. |
| **uv workspaces** | uv docs; audit C8 | Mudaria topologia do repo; é mérito, não factual. Revisitar se `security/` virar ponto de atrito. |

## 5. Riscos documentados (ganhos da pesquisa)

Estes riscos não estavam claros antes da pesquisa; agora estão registrados.

### 5.1. Stream completion risk (Huyen)

Se o agente gerar output via streaming, guardrails pós-LLM podem não capturar PII antes de um chunk parcial chegar ao usuário.
**Mitigação:** o template do agente desabilita streaming (`generate_content_config` sem stream). A camada 1 (OCR-side mask) já cobre o caso; a camada 2 (`before_model_callback`) roda pré-LLM, não pós — então o risco é residual, mas explicitado.
**Registrado em**: ADR-0003 § "Consequências".

### 5.2. Write-access sem aprovação humana (Huyen)

Nosso agente faz `POST /api/v1/appointments` autonomamente. Huyen alerta para exigir confirmação humana em write-actions produtivas.
**Mitigação no escopo atual:** agendamento é fictício, API é sandbox, `patient_ref` é anônimo. Risco real ≈ zero.
**Registrado em:** `docs/ARCHITECTURE.md` § "Classificação das tools" como observação.
**Se o desafio virasse produção:** introduzir `CONFIRMATION_REQUIRED` como flag no spec (campo novo → ADR nova).

### 5.3. Irreversible masking perde rastro (Huyen — reversible PII mapping)

Huyen sugere mascarar com mapeamento reversível (placeholder ↔ valor real num cofre) para desmascarar o output antes de entregar ao usuário. Nós escolhemos o oposto: **máscara irreversível + stable anon ref** (`patient_ref="anon-abc123"`).
**Motivo:** DESAFIO exige que PII nunca toque LLM nem persistência. Reversibilidade exigiria cofre → aumenta superfície de ataque sem ganho claro.
**Registrado em:** ADR-0003 § "Consequências".

### 5.4. Google ADK em churn (R-c da auditoria, reforçado por leitura)

Patterns de agentes estão em evolução rápida; APIs ADK já mudaram uma vez em 2026 (ver `DESIGN_AUDIT.md` C2). Continua ativo como risco.
**Mitigação:** pin de versão exata em `pyproject.toml` + CI.

## 6. Vocabulário (glossário curto para specs e ADRs)

Use estes termos literalmente em spec.md/plan.md/ADRs para que o código-review e a IA compartilhem referencial:

- **Plan-then-Execute**: gerar plano completo antes de executar qualquer tool call.
- **Assembled Reformat**: separar coleta de dados do passo de formatação final.
- **Trustworthy Generation**: output cita origem, score e correlation_id.
- **Reflection loop**: generate → critique → refine (ciclo do `code-reviewer`).
- **Tool inventory**: lista fechada de tools expostas; soft cap em ~13.
- **Write-action tool**: tool que muda estado externo; audit level reforçado.
- **Knowledge tool**: tool read-only; não muta nada.
- **Reversible PII mapping** *(rejeitado)*: placeholder ↔ valor real num cofre.
- **Irreversible mask + anon-ref** *(adotado)*: placeholder fixo + id anônimo estável.
- **Degraded mode**: caminho alternativo quando tool principal falha (ex.: `list_exams` top-5 em `E_RAG_NO_MATCH`).
- **LLM-as-Judge**: oracle baseado em LLM para avaliações subjetivas; último recurso.

## 7. Uso deste arquivo

- **Antes de abrir novo spec**: checar §1 (o padrão já existe?) e §4 (foi rejeitado? por quê?).
- **Ao escrever `instruction` do agente** (Bloco 6): consumir §2 como checklist.
- **Ao revisar (`code-reviewer`)**: usar §6 como vocabulário ao emitir findings.
- **Quando a stack mudar** (ex.: `gemini-2.5-flash` deprecated, ADK renomeia tudo de novo): revisitar §4 e §5.

Este arquivo é editável sem ADR — é contexto vivo da IA, não entrega ao avaliador.
