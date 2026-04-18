# Auditoria Crítica da Fase de Design Técnico

- **Data da auditoria**: 2026-04-18
- **Commits auditados**: `eca4bdf` (Preparação) e `3c35ad2` (Design Técnico).
- **Autor**: software-architect (auditor).
- **Princípio-guia**: *"Base all we produced in facts, not trusting entirely in the generated content so far."*
- **Política de correção**: em fase pré-implementação, **correções factuais** (API renomeada, modelo descontinuado, recognizer ausente) entram via `Edit` direto no arquivo afetado, com nota `> Corrigido em 2026-04-18 durante auditoria pré-implementação: …` nas ADRs. Mudanças de **mérito** (decisão-core trocada) sempre exigem ADR nova supersedendo. Essa regra termina no momento em que Bloco 1 começar.

## Verdict geral

**Design sólido para iniciar Bloco 1 após aplicar as correções inline listadas.**

- 2 achados **CRITICAL** corrigidos inline (C5 Gemini, C2 MCPToolset).
- 1 achado **MAJOR** corrigido inline (C6 Presidio BR).
- 1 achado **CRITICAL** mantido como risco documentado por exigência do desafio (C1 SSE).
- 5 achados **CONFIRMADOS**/`[OBSERVATION]` — nenhuma ação necessária.
- Nenhum achado exige ADR nova supersedendo (nenhuma mudança de **mérito**).
- Bloco 1 pode iniciar com as correções aplicadas.

---

## Claims externos auditados

### [CRITICAL] C5 — Gemini 2.0-flash está deprecated

**Claim auditado:** `docs/adr/0005-dev-stack.md` e `docs/adr/0006-spec-schema-and-agent-topology.md` fixam `gemini-2.0-flash` como modelo default via `Literal["gemini-2.0-flash"]` no schema.

**Fonte primária consultada:** https://ai.google.dev/gemini-api/docs/models (acesso 2026-04-18).

**Fato confirmado:** `gemini-2.0-flash` aparece na seção "Previous models" marcado como deprecated. Modelos atuais stable: `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`. `gemini-3.1-flash` está em preview. Alias `gemini-flash-latest` existe e aponta sempre para o flash mais novo.

**Verdict:** **DESATUALIZADO**.

**Impacto:** ADR-0005, ADR-0006, `docs/ARCHITECTURE.md` (schema + example JSON), `CLAUDE.md`, `.claude/agents/adk-mcp-engineer.md`, `ai-context/references/ADK.md`, `ai-context/LINKS.md`.

**Remediação proposta / aplicada:** troca inline de `gemini-2.0-flash` por `gemini-2.5-flash` em todos os arquivos. Mantido `Literal` (não alias) para preservar auditabilidade da mudança de modelo. Nota de correção adicionada ao final de ADR-0005 e ADR-0006.

**Diff resumido:**
- `ARCHITECTURE.md`: `Literal["gemini-2.0-flash"]` → `Literal["gemini-2.5-flash"]`; exemplo JSON idem.
- `adr/0005-dev-stack.md`: bullet + nota de correção.
- `adr/0006-spec-schema-and-agent-topology.md`: schema + consequências + nota de correção.
- `CLAUDE.md`: bullet dos princípios não-negociáveis.
- `ai-context/references/ADK.md`: exemplo + campo `model`.
- `.claude/agents/adk-mcp-engineer.md`: bullet de decisões ativas.
- `ai-context/LINKS.md`: seção Gemini atualizada.

---

### [CRITICAL] C2 — Classe `MCPToolset` / `SseConnectionParams` não existe mais no ADK

**Claim auditado:** ADR-0001, ADR-0006 e `ai-context/references/{ADK.md, MCP_SSE.md, TRANSPILER.md}` instruíam a consumir MCP via `MCPToolset(connection_params=SseConnectionParams(url=...))`.

**Fonte primária consultada:** https://adk.dev/tools-custom/mcp-tools/ (acesso 2026-04-18).

**Fato confirmado:** A classe correta é `McpToolset` (camelCase-ish, M minúsculo em `cp`). O único `connection_params` documentado para MCP remoto é `StreamableHTTPConnectionParams`. `SseConnectionParams` **não existe** no ADK atual. O exemplo oficial conecta a servidor SSE passando `StreamableHTTPConnectionParams(url=..., headers={"Accept": "application/json, text/event-stream", ...})` — a classe consome endpoints SSE via compat.

**Verdict:** **INCORRETO** (API renomeada + classe removida).

**Impacto:** ADR-0001, ADR-0006, `ai-context/references/ADK.md`, `ai-context/references/MCP_SSE.md`, `ai-context/references/TRANSPILER.md` (template Jinja do transpilador, crítico para Bloco 2), `.claude/agents/adk-mcp-engineer.md`.

**Remediação proposta / aplicada:** substituição inline em todos os arquivos. O template Jinja do transpilador já aponta para `StreamableHTTPConnectionParams` antes do primeiro commit de código — zero retrabalho futuro. Decisão-core (transporte SSE no servidor) preservada.

**Diff resumido:**
- `adr/0001-mcp-transport-sse.md`: snippet de consumo + nota de correção.
- `adr/0006-spec-schema-and-agent-topology.md`: texto de alternativas + nota.
- `ARCHITECTURE.md`: descrição do `generated_agent`.
- `ai-context/references/ADK.md` seção 4.2: import + classe.
- `ai-context/references/MCP_SSE.md` seção 4: snippet cliente.
- `ai-context/references/TRANSPILER.md` seção 7: template Jinja `agent.py.j2`.
- `.claude/agents/adk-mcp-engineer.md`: bullets de regras técnicas + decisões ativas.

---

### [CRITICAL] C1 — MCP SSE é oficialmente deprecated no MCP spec

**Claim auditado:** ADR-0001 diz: *"SSE tem suporte maduro no SDK `mcp[cli]`"* e que *"Se, após a entrega, o MCP oficial marcar SSE como deprecado, abrimos ADR nova"*.

**Fonte primária consultada:** https://modelcontextprotocol.io/docs/concepts/transports (acesso 2026-04-18 em auditoria anterior desta mesma sessão).

**Fato confirmado:** O spec atual define apenas **stdio** e **Streamable HTTP**. Nota oficial: *"This replaces the HTTP+SSE transport from protocol version 2024-11-05"*. Backwards-compatibility existe, mas o SSE é transporte "legado".

**Verdict:** **DESATUALIZADO** — porém a exigência literal do DESAFIO (`docs/DESAFIO.md` § "Requisitos Técnicos" — *"As ferramentas de OCR e RAG devem ser servidores MCP que se comunicam exclusivamente via Server-Sent Events (SSE)"*) é **imperativa**. Mantemos SSE no servidor.

**Impacto:** ADR-0001 (status da decisão), consumo do cliente (resolvido junto com C2 via `StreamableHTTPConnectionParams`).

**Remediação proposta / aplicada:** ADR-0001 ganha nota de correção reconhecendo a depreciação no spec MCP + risco de incompatibilidade futura documentado. A decisão **não muda** — DESAFIO impõe SSE. Não há ADR nova porque não há mudança de mérito. O cliente ADK consome via `StreamableHTTPConnectionParams` (ver C2), o que resolve a API-side; o servidor segue 100% SSE (`mcp.run(transport="sse", ...)`).

**Diff resumido:**
- `adr/0001-mcp-transport-sse.md`: nota de correção documenta a tensão DESAFIO vs spec.

---

### [CRITICAL] C6 — Presidio NÃO fornece recognizers brasileiros nativos

**Claim auditado:** `docs/ARCHITECTURE.md` e ADR-0003 tratavam `BR_CPF`/`BR_CNPJ`/`BR_RG`/`BR_PHONE` como se existissem no Presidio ou em lib comunitária instalável.

**Fonte primária consultada:** https://microsoft.github.io/presidio/supported_entities/ (acesso 2026-04-18).

**Fato confirmado:** Presidio cobre nativamente: US, UK, Spain, Italy, Poland, Singapore, Australia, India, Finland, Korea, Nigeria, Thailand. **Brasil não está listado.** Não há pacote comunitário consolidado conhecido que plugue recognizers BR direto no Presidio (busca em 2026-04 retorna libs standalone: `pycpfcnpj`, `brazilnum`, `brutils` — nenhuma delas é um adapter Presidio).

**Verdict:** **INCORRETO** (assumia feature inexistente).

**Impacto:** Bloco 5 (security-engineer) ganha ~0.5 pessoa-dia para escrever os 4 custom recognizers (`PatternRecognizer` do Presidio + regex + validação de dígito verificador via `pycpfcnpj`).

**Remediação proposta / aplicada:** correção inline em `docs/ARCHITECTURE.md` (tabela de entidades agora diz "custom recognizer") e em ADR-0003 (nota de correção + referências a `https://microsoft.github.io/presidio/supported_entities/` e `https://github.com/matheuscas/pycpfcnpj`). Decisão-core (dupla camada) **preservada** — só mudou a origem dos recognizers.

**Diff resumido:**
- `ARCHITECTURE.md` seção "Lista definitiva de entidades PII": coluna "Origem" reescrita.
- `adr/0003-pii-double-layer.md`: referências + nota de correção.

---

### [CONFIRMED] C3 — Parâmetro `instruction` (singular) está correto

**Claim auditado:** `docs/adr/0006-spec-schema-and-agent-topology.md` e `ai-context/references/ADK.md` usam `instruction` (singular) como parâmetro do `LlmAgent`.

**Fonte primária consultada:** https://adk.dev/agents/llm-agents/ (acesso 2026-04-18).

**Fato confirmado:** Docs oficiais usam `instruction="""You are an agent..."""` — **singular**. Keywords aceitos: `model`, `name`, `description`, `instruction`, `tools`, `generate_content_config`, `input_schema`, `output_schema`, `output_key`, `include_contents`, `planner`, `code_executor`.

**Verdict:** **CONFIRMADO**.

**Impacto:** nenhum — schema Pydantic (`AgentSpec.instruction: str`) e template Jinja já alinhados.

---

### [CONFIRMED] C4 — `before_model_callback` existe e pode mutar o prompt

**Claim auditado:** ADR-0003 assume que `before_model_callback` pode mutar o prompt antes de chegar ao LLM.

**Fonte primária consultada:** https://adk.dev/callbacks/ (acesso 2026-04-18).

**Fato confirmado:** Assinatura `def cb(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]`. Retorno `None` deixa a request (potencialmente mutada) passar; retorno `LlmResponse` curto-circuita o LLM. É possível iterar `llm_request.contents[].parts[].text` e substituir inline — exatamente o padrão de PII masking que a ADR-0003 descreve.

**Verdict:** **CONFIRMADO**.

**Impacto:** nenhum — decisão-core de dupla camada se mantém.

---

### [CONFIRMED] C7 — rapidfuzz API e threshold 80 estão corretos

**Claim auditado:** ADR-0007 usa `rapidfuzz.process.extractOne(query, choices, scorer=fuzz.WRatio, score_cutoff=80)` em escala 0–100.

**Fonte primária consultada:** https://rapidfuzz.github.io/RapidFuzz/Usage/process.html (acesso 2026-04-18).

**Fato confirmado:** Assinatura exata confirmada; `WRatio` é o scorer default; escala 0–100; `score_cutoff` filtra resultados abaixo do threshold e retorna `None` quando nenhum candidato passa.

**Verdict:** **CONFIRMADO**.

**Impacto:** nenhum — ADR-0007 mantida intacta.

---

### [OBSERVATION] C8 — uv workspaces existem e são viáveis, porém mantemos per-service pyproject por enquanto

**Claim auditado:** ADR-0005 escolhe "um `pyproject.toml` por serviço" sem considerar workspaces.

**Fonte primária consultada:** https://docs.astral.sh/uv/concepts/projects/workspaces/ (acesso 2026-04-18).

**Fato confirmado:** uv workspaces permitem múltiplos pacotes num lockfile único compartilhando dependências, com `{ workspace = true }` em `tool.uv.sources`. Permitiria consolidar `security/` como member importável pelos outros serviços sem duplicar. Docker integration não é explicitamente documentado, mas cada member tem seu próprio `pyproject.toml` — viável.

**Verdict:** **CONFIRMADO** (workspaces existem). Não aplicado porque representaria **mudança de mérito** na topologia do repo (exigiria ADR nova). Registrada como oportunidade de melhoria futura.

**Impacto:** nenhum agora; nota em `ai-context/LINKS.md` referencia esta seção. Se Bloco 7 descobrir duplicação dolorosa de dependências entre serviços, revisitar via ADR nova que supersede ADR-0005 na topologia.

---

### [CONFIRMED] C9 — spec-kit ainda usa `spec.md + plan.md + tasks.md` em `specs/NNNN-slug/`

**Claim auditado:** `docs/specs/README.md` baseia o método SDD em spec-kit, assumindo 3 artefatos e diretório `NNNN-slug/`.

**Fonte primária consultada:** https://github.com/github/spec-kit (acesso 2026-04-18).

**Fato confirmado:** Estrutura canônica `specs/001-<slug>/` com os três arquivos mantida. Frontmatter não é prescrito pelo spec-kit — nosso frontmatter (`linked_requirements`, `owner_agent`, etc.) é uma extensão compatível.

**Verdict:** **CONFIRMADO**.

**Impacto:** nenhum.

---

### [CONFIRMED] C10 — ADK não oferece scaffolding de agente a partir de spec

**Claim auditado:** ADR-0002 justifica construir transpilador próprio (Jinja2 + `ast.parse`); nenhum ADR considerou se o ADK já oferece essa função.

**Fonte primária consultada:** https://adk.dev/ (acesso 2026-04-18).

**Fato confirmado:** ADK não expõe comando `adk create <spec.json>` ou gerador declarativo. Padrão esperado: escrever código Python diretamente. Há menção a "Visual Builder" em navegação mas sem funcionalidade documentada de ingestão de spec.

**Verdict:** **CONFIRMADO** (transpilador próprio é justificado).

**Impacto:** nenhum — ADR-0002 preservada.

---

## Checagens internas

### [OBSERVATION] I1 — Cross-references entre `docs/ARCHITECTURE.md` ↔ ADRs ↔ `ai-context/references/*`

Os arquivos referenciados existem:

- `ai-context/references/ADK.md` — presente.
- `ai-context/references/MCP_SSE.md` — presente.
- `ai-context/references/TRANSPILER.md` — presente.
- `ai-context/references/PII.md` — não encontrado (referenciado em ADR-0003). **Ação:** marcar como "a criar durante Bloco 5" (security-engineer). Não é blocker do Bloco 1.

### [OK] I2 — Entidades PII vs. Presidio

Corrigido via C6. Entidades stock (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME) estão em Presidio global; as BR são custom. Tabela em `ARCHITECTURE.md` reflete a realidade.

### [OK] I3 — Tool signatures MCP

`ARCHITECTURE.md` (seção "Assinaturas exatas das tools MCP") ↔ ADR-0001 ↔ ADR-0007 consistentes. `search_exam_code` retorna `ExamMatch | None` — casa com threshold rapidfuzz (C7).

### [OK] I4 — Taxonomia de erros

Cada código tem módulo dono. Nenhum conflito. `E_PII_ENGINE` e `E_PII_LANGUAGE` → `security`; `E_MCP_*` → `generated_agent`; `E_RAG_NO_MATCH` → `rag_mcp`; etc.

### [OK] I5 — R01..R12 cobrem DESAFIO.md

Mapeamento conferido contra `docs/DESAFIO.md`:

- "Transpilador" (§ O que você vai construir) → R01. ✓
- "MCP OCR/SSE" (§ passos 2 + Req. Técnicos) → R02. ✓
- "RAG ≥ 100 exames" (§ passo 3) → R03. ✓
- "FastAPI Swagger" (§ passo 4 + Req. Técnicos) → R04. ✓
- "Camada PII" (§ Req. Técnicos) → R05. ✓
- "Agente end-to-end" (§ passo 5) → R06. ✓
- "Docker + compose" → R07. ✓
- "Evidências" → R08. ✓
- "README PT" + "Transparência IA" → R09, R12. ✓
- "Imagem de teste + JSON exemplo" → R10. ✓
- "Mock OCR" → R11 (decisão interna documentada). ✓

Requisitos escondidos não identificados — nenhum detalhe literal do DESAFIO ficou sem R correspondente.

### [OK] I6 — Topologia LlmAgent único atende OCR → RAG → API

Confirmado por C10 (sem scaffolding ADK alternativo) + C4 (callbacks funcionam) + C3 (instruction orquestra linguisticamente). Alternativas `SequentialAgent`/`ParallelAgent` existem no ADK (confirmado em `ADK.md` seção 3.2) mas não são necessárias para fluxo linear.

### [OK] I7 — Log format + correlation_id honrados

`ARCHITECTURE.md` seção "Formato de log" define `correlation_id` propagado via header `X-Correlation-ID` (HTTP) e metadata MCP. FastAPI e FastMCP ambos suportam middleware/hooks para injetar. Não vi contradição nos ADRs. Implementação prática fica para Blocos 3/4.

---

## Riscos reavaliados

### [TRATADO] R-a — Gemini 2.0-flash ser descontinuado

Já materializado (C5). Corrigido inline para `gemini-2.5-flash`. `Literal` no schema continua forçando revisão consciente na próxima troca.

### [TRATADO] R-b — Presidio BR recognizers não existirem

Já materializado (C6). Custo extra (~0.5 pessoa-dia) absorvido no Bloco 5 sem mudança de decisão-core.

### [ATIVO] R-c — `google-adk` em churn

Mitigado mas não eliminado. Já vimos mudança: `SseConnectionParams` removido, classe consolidada em `StreamableHTTPConnectionParams`. **Ação preventiva:** fixar versão exata do `google-adk` em cada `pyproject.toml` (sem `>=`), e rodar CI contra ela. Se uma nova auditoria for necessária no futuro, repetir esse processo.

### [OBSERVAÇÃO] R-d — Ambiguidade do termo "RAG" no DESAFIO

DESAFIO.md diz *"pesquisa os detalhes … através de RAG"*. Implementamos fuzzy match com rapidfuzz (ADR-0007) — tecnicamente é **retrieval** sobre um catálogo, mas não usa embeddings. **Ação:** documentar essa escolha de forma explícita na seção "Transparência e Uso de IA" do README final (R12) + no próprio ADR-0007 ("por que não embeddings"). Avaliador precisa entender que foi decisão consciente, não lacuna.

### [MITIGADO] R-e — PII `before_model_callback` não cobrir tool-to-tool chatter

Parcialmente mitigado pela dupla camada (OCR já mascara). Em tool-to-tool no ADK, o callback roda **antes de cada chamada ao LLM** — então se o LLM fizer outra tool call depois de receber PII de uma tool, a segunda chamada passa pelo callback. O risco residual é se a tool persistir antes de retornar; por isso a camada no OCR é não-negociável (ADR-0003 já cobre).

---

## Arquivos tocados nesta auditoria

### Correções factuais inline (com nota nas ADRs)

- `docs/adr/0001-mcp-transport-sse.md` — snippet de consumo + nota de correção.
- `docs/adr/0003-pii-double-layer.md` — referências atualizadas + nota de correção.
- `docs/adr/0005-dev-stack.md` — modelo Gemini + URLs + nota de correção.
- `docs/adr/0006-spec-schema-and-agent-topology.md` — schema Literal + classe MCP + nota de correção.

### Correções factuais inline (sem nota — arquivos de trabalho)

- `docs/ARCHITECTURE.md` — schema, example JSON, tabela PII, descrição do generated_agent.
- `CLAUDE.md` — princípio da stack fechada.
- `.claude/agents/adk-mcp-engineer.md` — bullets técnicos e decisões ativas.
- `ai-context/references/ADK.md` — exemplos de código + campo `model`.
- `ai-context/references/MCP_SSE.md` — snippet cliente.
- `ai-context/references/TRANSPILER.md` — template Jinja `agent.py.j2`.
- `ai-context/LINKS.md` — seções ADK, Gemini, Presidio, uv (novas URLs).

### Arquivo novo

- `ai-context/references/DESIGN_AUDIT.md` — este laudo.

### Arquivo ADR novo

- **Nenhum.** Nenhuma mudança de mérito foi identificada pela auditoria.

---

## Fontes externas consultadas (todas adicionadas a `ai-context/LINKS.md`)

- https://ai.google.dev/gemini-api/docs/models — C5 Gemini.
- https://adk.dev/agents/llm-agents/ — C3 LlmAgent signature.
- https://adk.dev/tools-custom/mcp-tools/ — C2 McpToolset.
- https://adk.dev/callbacks/ — C4 before_model_callback.
- https://adk.dev/ — C10 ADK scaffolding.
- https://modelcontextprotocol.io/docs/concepts/transports — C1 MCP SSE status.
- https://microsoft.github.io/presidio/supported_entities/ — C6 Presidio entidades.
- https://rapidfuzz.github.io/RapidFuzz/Usage/process.html — C7 rapidfuzz.
- https://docs.astral.sh/uv/concepts/projects/workspaces/ — C8 uv workspaces.
- https://github.com/github/spec-kit — C9 SDD.
- https://github.com/matheuscas/pycpfcnpj — recognizer BR helper.

---

## Recomendação final

**Bloco 1 pode ser iniciado.** Todas as correções factuais foram aplicadas; nenhuma decisão-core foi revertida; nenhuma ADR nova é necessária. A política de edit-inline pré-implementação consumiu zero ADRs supersedentes, evitando acumular "AI slop". A partir do primeiro commit de código contra qualquer ADR, a regra clássica de imutabilidade volta a valer.

Qualquer nova falha factual descoberta durante implementação **depois** do primeiro commit de código vira ADR nova — não mais edit inline.
