---
id: 0006-generated-agent
title: Agente ADK end-to-end consumindo OCR + RAG + API com PII dupla camada
status: approved
linked_requirements: [R06]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O agente gerado é o **protagonista** do fluxo end-to-end: recebe uma imagem via CLI, chama OCR, mapeia cada exame em código via RAG, agenda na API e imprime tabela final com códigos + ID de agendamento + rastreio (ver diagrama de fluxo em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)). Sem este bloco, os Blocos 3, 4 e 5 são servidores inertes.

A instrução deste agente precisa incorporar o backlog de patterns explicitado em [`ai-context/references/AGENTIC_PATTERNS.md`](../../../ai-context/references/AGENTIC_PATTERNS.md) § 2: **plan-then-execute**, **assembled reformat**, **trustworthy generation**, **parameter inspection**, **exception handling com retry/fallback**.

- O que falta hoje? Um `spec.json` concreto (`spec.example.json`) + o pacote `generated_agent/` gerado pelo transpilador + a cadeia PII dupla (ADR-0003) + uma CLI para rodar o fluxo.
- Quem é afetado? Avaliador (roda o E2E), `devops-engineer` (empacota em container), `qa-engineer` (escreve E2E).
- Por que importa agora? É o entregável central do desafio — agente funcional orquestrando tudo.

## User stories

- Como **avaliador**, quero rodar `adk run generated_agent --image ./docs/fixtures/sample_medical_order.png` e ver no terminal: lista de exames com códigos + ID do agendamento criado.
- Como **paciente (proxy via `patient_ref` anônimo)**, quero que nenhum valor de PII chegue ao Gemini nem à API nem aos logs.
- Como **avaliador**, quero que a saída final cite origem, score e `correlation_id` (pattern **trustworthy generation**) para distinguir fato de alucinação.
- Como **agente**, quero cair em modo degradado (`list_exams` top-5) quando `search_exam_code` retorna `None` para o exame.

## Critérios de aceitação

### Orquestração (plan-then-execute)

- [AC1] Dado `sample_medical_order.png` com 3 exames reconhecidos, quando a CLI roda, então o agente realiza **no máximo 5 tool calls** no total (1 OCR + até 3 RAG + 1 POST) para completar o fluxo — verificado via contagem nos logs `event=tool.called` (pattern plan-then-execute).
- [AC2] Dado OCR retorna N exames, quando o agente busca códigos, então as N chamadas a `search_exam_code` ocorrem em **paralelo** (múltiplas tool calls na mesma resposta do Gemini) — verificado no log por janela temporal de chamadas simultâneas (pattern parallelization).
- [AC3] Dado RAG retorna matches para todos os exames, quando o agente chama `POST /api/v1/appointments`, então envia **uma única** requisição com todos os exames no campo `exams[]` — nunca um POST por exame (pattern assembled reformat).

### Segurança PII dupla (ADR-0003)

- [AC4] Dado qualquer execução, quando o corpo enviado ao Gemini (capturável via hook de teste do ADK) é inspecionado, então **não contém** valores que casem com entidades PII listadas em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva" — segunda linha via `before_model_callback` (ADR-0003).
- [AC5] Dado qualquer POST ao `scheduling-api`, quando o body é inspecionado, então o campo `patient_ref` casa o regex `^anon-[a-z0-9]+$` e **não** contém nome cru.

### Integração

- [AC6] Dado o agente configurado com `OCR_MCP_URL=http://ocr-mcp:8001/sse` e `RAG_MCP_URL=http://rag-mcp:8002/sse`, quando inicializado, então descobre via MCP as tools `extract_exams_from_image`, `search_exam_code`, `list_exams` — verificado em teste de inicialização.
- [AC7] Dado o agente configurado com `SCHEDULING_API_URL=http://scheduling-api:8000` e `openapi_url` apontando para `/openapi.json`, quando inicializado, então a tool HTTP para `POST /api/v1/appointments` aparece no inventory do agente.
- [AC8] Dado um exame para o qual RAG retorna `None`, quando o agente continua, então chama `list_exams(limit=5)` e exibe ao usuário sugestões — pattern **degraded mode** (Gulli Ch 12).

### Saída final (trustworthy generation)

- [AC9] Dada uma execução bem-sucedida, quando o output final é impresso, então para cada exame a linha mostra: `<nome> → <code> (rag-mcp, score=<float>, correlation_id=<id>)` — e na última linha o ID do agendamento e o status.
- [AC10] Dado um match de RAG com `score < 0.80`, quando exibido, então é explicitamente marcado como "não-conclusivo" em vez de reportado como match válido (threshold ADR-0007).

### Observabilidade

- [AC11] Dado qualquer execução, quando os logs são inspecionados, então cada chamada de tool emite `event=tool.called` com `params_hash` (sha256 prefix), `duration_ms`, `correlation_id` (pattern parameter inspection).
- [AC12] Dado qualquer execução, quando inspecionada, então existe exatamente um `correlation_id` propagado desde a CLI até o log do `scheduling-api` (via header `X-Correlation-ID`).

### Fixtures

- [AC13] O repositório inclui `docs/fixtures/sample_medical_order.png` (R10) e `spec.example.json` (R10).

### Retry/fallback (política congelada)

- [AC14] Dado que `rag-mcp.search_exam_code` retorna `None` para um exame, quando o agente processar, então ele deve chamar `list_exams(limit=20)` e apresentar os top candidatos ao usuário pedindo confirmação/correção antes de reportar erro (zero retry em `E_RAG_NO_MATCH`).
- [AC15] Dado que uma chamada MCP levanta `E_MCP_TIMEOUT`, quando o agente lida com o erro, então executa **exatamente 1 retry** com delay fixo de 500 ms; se persistir, propaga `ChallengeError` com `hint` citando `docker compose ps`.
- [AC16] Dado que `POST /api/v1/appointments` retorna 422 (`E_API_VALIDATION`), quando o agente lida com o erro, então **não faz retry** (agendamento duplicado é inaceitável) e reporta ao usuário o `<campo>` + `<motivo>` extraído da mensagem Pydantic.

### Guardrails de execução (ADR-0008)

- [AC18] Dada uma execução do agente, quando o processamento total excede 300 segundos, então a CLI aborta com `ChallengeError(code="E_AGENT_TIMEOUT")` conforme [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md); nenhum agendamento parcial é registrado.
- [AC19] Dada uma saída do LLM Gemini que não casa o schema esperado (ex.: JSON malformado, campo `exams` ausente), quando o runner tenta parsear, então levanta `ChallengeError(code="E_AGENT_OUTPUT_INVALID")` com `hint` indicando validação do output do LLM; **zero retry** — reporta ao usuário e aborta.
- [AC20] Dada a `instruction` do `spec.example.json`, quando medida em bytes UTF-8, então é ≤ 4096 bytes conforme NFR de cache de prompt do Gemini; `transpiler.load_spec` rejeita spec com `instruction` > cap via ADR-0008 (reforço do AC11 do Bloco 1).
- [AC21] Dado qualquer log emitido pelo agente ou pelo runner CLI, quando inspecionado, então **nenhum campo** contém valor PII cru (padrões definidos em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII") — reforço da regra "no-PII-in-logs" de [ADR-0008 § No-PII-in-logs](../../adr/0008-robust-validation-policy.md).

### Saída formatada final

- [AC17] Dada uma execução bem-sucedida, quando o output final é impresso, então é uma **tabela ASCII puro** (sem Rich, sem cores ANSI) no formato literal abaixo, verificado por snapshot test:

  ```
  +-----+------------------------+---------+
  | #   | Exame                  | Código  |
  +-----+------------------------+---------+
  | 1   | Hemograma Completo     | HMG-001 |
  | 2   | Glicemia de Jejum      | GLJ-002 |
  +-----+------------------------+---------+
  Appointment ID: apt-42  |  Scheduled: 2026-05-01T09:00Z
  ```

## Robustez e guardrails

### Happy Path

Avaliador roda `python -m generated_agent --image ./docs/fixtures/sample_medical_order.png` → agente executa OCR (1 call) + RAG em paralelo (3 calls) + POST (1 call), imprime tabela ASCII com 3 exames + appointment ID em < 60 s, com `correlation_id` único propagado.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| Execução > 300 s | abort hard | `E_AGENT_TIMEOUT` | AC18 |
| Output do LLM malformado | zero retry + abort | `E_AGENT_OUTPUT_INVALID` | AC19 |
| `instruction` > 4 KB no spec | rejeição via Bloco 1 | `E_TRANSPILER_SCHEMA` | AC20 |
| Log contém padrão PII | auditoria rejeita | — | AC21 |
| `E_MCP_TIMEOUT` | 1 retry 500 ms | — | AC15 |
| `E_RAG_NO_MATCH` | zero retry, modo degradado | — | AC14 |
| `E_API_VALIDATION` | zero retry, reporta | — | AC16 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| Execução total do agente | 300 s | `E_AGENT_TIMEOUT` | AC18 |
| `instruction` (bytes UTF-8) | 4096 | `E_TRANSPILER_SCHEMA` | AC20 |

### Security & threats

- **Ameaça**: agente entra em loop de tool calls e consome budget de Gemini + trava recursos.
  **Mitigação**: timeout de 300 s (AC18); AC1 (≤ 5 tool calls) reforça. Falha reporta ao usuário; nenhum agendamento parcial.
- **Ameaça**: Gemini alucina campos e runner cria agendamento com dados inválidos.
  **Mitigação**: validação estrita do output do LLM (AC19); zero retry em `E_AGENT_OUTPUT_INVALID`.
- **Ameaça**: `instruction` inflada passa > 4 KB e vaza cache de prompt, degradando latência.
  **Mitigação**: cap congelado em ADR-0008 via Bloco 1 (AC20); validação acontece no transpilador.
- **Ameaça**: log emite valor cru (nome, CPF) recebido da tool OCR após PII mask falhar.
  **Mitigação**: dupla camada PII (ADR-0003); teste T029 valida caplog do runner (AC21).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC4 | `root_agent` | Invariant (`before_model_callback` registrado) |
| AC14, AC15, AC16 | Retry policy (contrato textual no `instruction`) | Post |
| AC18 | Runner CLI (`generated_agent/__main__.py`) | Post (timeout 300 s ADR-0008) |
| AC19 | Runner CLI | Post (validação de output do LLM) |
| AC20 | `AgentSpec.instruction` | Invariant (cap 4 KB ADR-0008) |
| AC21 | Agent + runner logging | Invariant (no-PII-in-logs ADR-0008) |

## Requisitos não-funcionais

- **Streaming desativado** (ADR-0003 § "Risco operacional: stream completion").
- **Retry policy** conforme backlog (AGENTIC_PATTERNS § 2.6): 1 retry com backoff 500 ms em `E_MCP_TIMEOUT`; `E_RAG_NO_MATCH` → modo degradado; `E_API_VALIDATION` → sem retry, reporta ao usuário.
- **Determinismo relativo**: dado o mesmo input, o fluxo de tools segue a mesma sequência (o texto final varia naturalmente por ser LLM).
- **Tokens**: a instrução do agente fica < 4 KB para caber em cache de prompt do Gemini (inspeção manual).

## Clarifications

*(nenhuma — todas as políticas (retry/fallback, formato da tabela, conteúdo da fixture PNG) foram fixadas.)*

## Fora de escopo

- Orquestrator-worker / SequentialAgent (ADR-0006 rejeita no MVP).
- Streaming (explicitamente desativado — ADR-0003).
- Suporte a múltiplas imagens em uma execução.
- Re-humanização do output (máscara é irreversível — ADR-0003).
- Cache semântico ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Camadas conscientemente omitidas").
