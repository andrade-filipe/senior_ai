---
id: 0010-pre-ocr-invocation
title: Pre-OCR invocation — CLI orquestra o OCR antes do LlmAgent
status: approved
linked_requirements: [R02, R06, R08, R11]
owner_agent: software-architect
created: 2026-04-20
---

## Problema

A spec 0009 Camada A instrumentou o server OCR com o log `ocr.lookup.hash` (T041). Na primeira execução E2E real (2026-04-20, `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`, `GEMINI_MODEL=gemini-2.5-pro`) a evidência foi conclusiva:

- A imagem em disco é `sample_medical_order.png`, 9469 bytes, sha256 `17c46fa55aa8d2178cc66ffd80db10f335adea473c58a1c297c4091c1834f93b`. A CLI loga corretamente `agent.run.start` com `image_sha256_prefix=17c46fa5`.
- A tool `extract_exams_from_image` do OCR MCP recebeu, em dois turnos seguidos, **hashes diferentes** — `1b11b0e341d6…` (184 bytes) e `e150238a669e…` (223 bytes). Ambos são **PNGs minúsculos inventados pelo próprio Gemini**; nenhum deriva dos bytes reais que a CLI empacotou em `Part.from_bytes`.

A causa é arquitetural. O `LlmAgent` recebe a imagem como `inline_data` (blob binário) e a tool exige um argumento `image_base64: str`. **O modelo não tem uma primitiva que referencie os bytes do Part visual dentro de uma function-call**: ele só pode produzir uma string; e como o prompt pede "passe a imagem em base64", ele fabrica um base64 arbitrário (tipicamente um PNG 1×1 vazio). Esse design **nunca poderia funcionar** com imagens reais — e o `FIXTURES` dict do OCR, por construção (hash determinístico do arquivo correto), devolve `[]` para os PNGs alucinados. O agente segue sem lista de exames, faz `POST /appointments` vazio, toma 422 e o CLI termina com `E_AGENT_OUTPUT_INVALID`.

Afeta: **o avaliador do desafio**, que roda o comando canônico e não vê a tabela ASCII; o **operador**, que não consegue substituir a fixture porque o bug não depende do arquivo; o **autor do CLI**, cujo contrato de tool é insatisfazível para input binário; e o **engenheiro de resiliência**, pois as Camadas B/C da 0009 sozinhas não substituem a lista de exames ausente — elas tornam o fracasso mais legível, não o evitam.

Por que importa agora: é o último bloqueio antes do E2E verde reprodutível. Sem pré-OCR determinístico, todo o trabalho feito em 0001–0009 não "aparece" na entrega. A spec 0009 permanece válida nas Camadas B e C (envelope tolerante, validator-pass); a Camada A (fixture reliability no tool call do modelo) fica **partialmente superseded** por esta spec 0010.

## User stories

- Como **avaliador do desafio**, eu quero rodar `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` e ver a tabela ASCII com `appointment_id` **determinísticamente**, para que eu confirme o happy path sem depender da capacidade do modelo de "reencaminhar" bytes.
- Como **operador**, eu quero substituir a fixture por outra imagem registrada via `register_fixture(path, exams)` e que o CLI chame o OCR diretamente, para que eu exercite o sistema com pedidos sintéticos distintos **sem precisar reeducar o modelo**.
- Como **autor da CLI**, eu quero que a CLI seja o orquestradora do passo de OCR, para que o agente receba uma lista textual já extraída e o contrato de tool deixe de exigir argumento binário.
- Como **engenheiro de resiliência**, eu quero que um fallback `E_MCP_UNAVAILABLE` explícito (sem envolver o LlmAgent) exista para o caso de o OCR-MCP estar down, para que falhas de infra não se misturem com falhas do modelo.

## Critérios de aceitação

- [AC1] Dada uma imagem válida em `--image`, quando a CLI inicia, então ela chama `extract_exams_from_image(image_base64)` via MCP-SSE client **antes** de `runner.run_async`, e emite log `agent.preocr.invoked` com `sha256_prefix` dos bytes lidos.
- [AC2] Dado que o OCR-MCP retorna lista vazia (ou `ToolError` `E_OCR_UNKNOWN_IMAGE`), quando a CLI processa, então aborta com envelope canônico `E_OCR_UNKNOWN_IMAGE` (exit `4` — reaproveitado da Camada B da 0009) **sem** invocar o `LlmAgent`.
- [AC3] Dado que o pré-OCR devolve lista não-vazia, quando a CLI monta o prompt, então o `Content` enviado ao runner contém **uma única Part de texto** no formato canônico `"EXAMES DETECTADOS (OCR pré-executado pelo CLI): <json-array>\n\n<instrucao-padrao>"` e **não** contém `inline_data`.
- [AC4] Dado o agente instanciado por `_build_agent(correlation_id)`, quando a topologia é montada, então o McpToolset do OCR **não** expõe `extract_exams_from_image` ao modelo (`tool_filter=[]` ou toolset ausente). A tool continua existindo no server OCR para uso direto da CLI.
- [AC5] Dado o E2E real com `.env` default (ADR-0009 / `GEMINI_MODEL=gemini-2.5-flash-lite`), quando `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` roda, então exit `0`, stdout contém a tabela ASCII, `appointment_id` presente, e `docs/EVIDENCE/0010-pre-ocr-invocation.md` captura o transcript.
- [AC6] Dado que o OCR-MCP não está healthy (`sse_client` estoura `PREOCR_MCP_TIMEOUT_SECONDS`), quando a CLI processa, então aborta com envelope `E_MCP_UNAVAILABLE` (novo na taxonomia), exit `5` (novo), **sem** invocar o `LlmAgent`.
- [AC7] Dado qualquer caminho do pré-OCR, quando executado, então emite logs estruturados: `agent.preocr.invoked` (start), `agent.preocr.result{exam_count, duration_ms}` (success), `agent.preocr.timeout` (timeout), `agent.preocr.error{error_code}` (outros erros). Todos incluem `correlation_id`.
- [AC8] Dado que `transpiler/` evolui para emitir o `McpToolset` sem expor a tool OCR, quando `uv run pytest transpiler/tests/test_snapshots.py -q` roda, então verde, com snapshot atualizado refletindo a nova topologia.

## Robustez e guardrails

### Happy Path

CLI lê bytes do `--image` → encoda em base64 → abre SSE session para `OCR_MCP_URL` → `session.call_tool("extract_exams_from_image", {"image_base64": b64})` → recebe lista `["Hemograma Completo", …]` → monta `Content` textual → `runner.run_async` executa passos 2–6 do plano (RAG em paralelo, scheduling, JSON final) → CLI valida contra `RunnerSuccess`, imprime tabela, exit `0`.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| OCR devolve lista vazia | CLI aborta sem LlmAgent | `E_OCR_UNKNOWN_IMAGE` (exit 4) | AC2 |
| OCR levanta `ToolError[E_OCR_IMAGE_TOO_LARGE]` | CLI propaga o código via envelope | `E_OCR_IMAGE_TOO_LARGE` (exit 1) | AC2 (parcial) |
| OCR levanta `ToolError[E_OCR_INVALID_INPUT]` | CLI propaga | `E_OCR_INVALID_INPUT` (exit 1) | AC2 (parcial) |
| OCR levanta `ToolError[E_OCR_TIMEOUT]` | CLI propaga | `E_OCR_TIMEOUT` (exit 2) | AC2 (parcial) |
| SSE connect estoura `PREOCR_MCP_TIMEOUT_SECONDS` | CLI aborta | `E_MCP_UNAVAILABLE` (exit 5) | AC6 |
| `session.call_tool` estoura timeout | idem | `E_MCP_UNAVAILABLE` (exit 5) | AC6 |
| Tentativa de transporte falha (`ConnectError`) | retry única (`PREOCR_MCP_CONNECT_RETRIES=1`); persiste → aborta | `E_MCP_UNAVAILABLE` (exit 5) | AC6 |
| OCR retorna lista com strings vazias | CLI trata como vazia (AC2) | `E_OCR_UNKNOWN_IMAGE` (exit 4) | AC2 |
| Imagem muito grande (> `OCR_IMAGE_MAX_BYTES`) | OCR rejeita; CLI propaga o erro original | `E_OCR_IMAGE_TOO_LARGE` (exit 1) | AC2 (parcial) |

### Guardrails

| Alvo | Cap / Timeout | Violação | AC ref |
|---|---|---|---|
| `PREOCR_MCP_TIMEOUT_SECONDS` (env) | default `10` s | abort `E_MCP_UNAVAILABLE` | AC6 |
| `PREOCR_MCP_CONNECT_RETRIES` (env) | default `1` | abort após a tentativa extra | AC6 |
| `AGENT_TIMEOUT_SECONDS` (env, ADR-0009) | default `300` s | abort `E_AGENT_TIMEOUT` (inalterado) | — |
| Fixture existente (`OCR_IMAGE_MAX_BYTES`) | default `5 MB` | erro propagado do OCR | AC2 (parcial) |

### Security & threats

- **Ameaça**: CLI chamando SSE direto expande a surface de credenciais/cabeçalhos no binário do cliente.
  **Mitigação**: nenhuma credencial nova. `OCR_MCP_URL` é a mesma URL interna do compose; `X-Correlation-ID` é gerado na CLI (como hoje para o LlmAgent). Nada sai do network do compose.
- **Ameaça**: imagem agora passa pela CLI (já passava), e o OCR-MCP pode receber bytes de um caller confiável (CLI) ou de um modelo "do futuro" (hoje desativado).
  **Mitigação**: OCR-MCP continua aplicando PII mask (ADR-0003 Layer 1) em qualquer input; nenhuma regressão.
- **Ameaça**: erro silencioso se a retry extra mascarar um problema persistente de rede.
  **Mitigação**: retry registrada com log `agent.preocr.connect.retry`; `PREOCR_MCP_CONNECT_RETRIES=0` disponível para desligar.

### Rastreabilidade DbC

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC1 | `_run_preocr` | Post (emite log + retorna lista) |
| AC2 | `main` | Post (exit 4 sem runner) |
| AC3 | `_build_preocr_prompt` | Post (Part textual única, sem inline_data) |
| AC4 | `_build_agent` (regenerado) | Invariant (tool OCR fora do filter) |
| AC6 | `_run_preocr` | Invariant (timeout absoluto + fallback) |
| AC7 | `_run_preocr` | Post (logs estruturados) |

## Requisitos não-funcionais

- **Desempenho**: pré-OCR adiciona 1 round-trip SSE ao servidor local (p50 < 200 ms, p99 < 1 s dentro do compose). Não aumenta o custo de tokens — pelo contrário: reduz, pois o modelo não volta a "chamar OCR" num segundo turno.
- **Observabilidade**: todos os logs pré-OCR compartilham `correlation_id` com a sessão ADK subsequente — rastreio contínuo via `grep`.
- **Operabilidade**: feature flag não requerida; a mudança é determinística e deve valer em todos os ambientes. Timeout e retry são env (ADR-0009).
- **Segurança**: idem ADR-0003 Layer 1; sem delta.

## [NEEDS CLARIFICATION]

Nenhum. As quatro decisões pendentes já estão resolvidas neste spec:

- [x] Timeout pré-OCR: `PREOCR_MCP_TIMEOUT_SECONDS=10` (alinhado com `SCHEDULING_OPENAPI_FETCH_TIMEOUT_SECONDS` e com o `OCR_TIMEOUT_SECONDS` do próprio server).
- [x] Retry: `PREOCR_MCP_CONNECT_RETRIES=1`, apenas para `ConnectError` (cobre flakiness de startup dentro do compose).
- [x] Onde expor a lista no prompt: prefixo de texto antes da instrução fixa, formato canônico `"EXAMES DETECTADOS (OCR pré-executado pelo CLI): <json-array>"`.
- [x] Manter ou remover a tool do MCP: **manter no server** (API pública útil para tests/scripts); **não expor ao modelo** (`tool_filter=[]` no McpToolset).

## Fora de escopo

- Reescrita completa do prompt fixo — edição cirúrgica apenas (passo 1 "chame extract_exams…" sai; passo 1 "você recebeu o bloco EXAMES DETECTADOS" entra).
- Introdução de composição de agentes (`SequentialAgent`) — ADR-0006 mantido nesse recorte.
- Fixtures OCR por hash perceptual — overkill; fora do escopo de 0009 também.
- Imagens que não sejam PNG/JPEG — schema do OCR-MCP inalterado.
- Mudança do modelo default ou dos caps de PII — cobertos por ADR-0009 / ADR-0003.

## Atualização 2026-04-20 — relação com spec 0009

- **Camada A** (fixture reliability no tool call do modelo) fica **partialmente superseded** por esta spec 0010. `register_fixture` permanece implementado (API pública útil); AC1/AC2 da 0009 são reinterpretados no nível da CLI (pré-OCR), não mais no nível do modelo.
- **Camada B** (RunnerSuccess | RunnerError tolerante) continua válida e necessária — o agente pode falhar em etapas posteriores à extração.
- **Camada C** (validator-pass opcional) continua válida.
