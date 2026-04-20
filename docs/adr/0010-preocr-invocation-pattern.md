# ADR-0010: Pré-OCR invocado pelo CLI (CLI-orchestrated pre-step)

- **Status**: accepted
- **Data**: 2026-04-20
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação — 2026-04-20, pós-pesquisa de validação)

## Contexto

Em 2026-04-20, durante o E2E real da entrega (`docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`, `GEMINI_MODEL=gemini-2.5-pro`), o log estruturado `ocr.lookup.hash` instrumentado pela spec 0009 (T041) expôs um problema arquitetural até então invisível: **o Gemini não consegue reencaminhar os bytes do Part visual (`inline_data`) como argumento string (`image_base64`) de uma function-call**. O modelo recebe a imagem como blob binário; quando precisa chamar uma tool que espera `image_base64: str`, ele **inventa** um base64 arbitrário — tipicamente um PNG 1×1 (observado: 184 e 223 bytes) — porque não há primitiva no SDK `google-genai` que permita referenciar os bytes do Part dentro do argumento da função.

Evidência bruta (log filtrado):

```
"event": "agent.run.start", "image_sha256_prefix": "17c46fa5"    # arquivo real, 9469 bytes
"event": "ocr.lookup.hash", "sha256_prefix": "1b11b0e341d6", "payload_bytes": 184   # alucinado
"event": "ocr.lookup.hash", "sha256_prefix": "e150238a669e", "payload_bytes": 223   # alucinado
```

Isso invalida a premissa do ADR-0006 no recorte "LlmAgent único com tool de OCR aceitando `image_base64`". A topologia (`LlmAgent` + `McpToolset` + PII callback) continua válida; o que não funciona é **deixar o modelo produzir o argumento binário**. Sem intervenção, o OCR devolve `[]`, o agente segue vazio, `POST /appointments` falha com 422, o modelo inventa envelope de erro e a CLI sai com `E_AGENT_OUTPUT_INVALID`.

## Alternativas consideradas

1. **Pre-OCR no CLI (escolhida — Path X)** — a CLI chama `extract_exams_from_image` via cliente MCP-SSE antes do `runner.run_async` e injeta a lista de exames como texto no prompt. O LlmAgent nunca vê a imagem.
   - Prós: determinístico, elimina a dependência de capacidade especulativa do modelo; reduz tokens (sem inline_data); preserva topologia de LlmAgent único de ADR-0006; mantém OCR-MCP como serviço público (testável); PII Layer 1 continua valendo.
   - Contras: CLI assume responsabilidade orquestradora adicional; se OCR-MCP cair, nenhum run acontece (mitigado pelo `depends_on: service_healthy` da Onda 4 + `E_MCP_UNAVAILABLE` novo).
2. **Image-by-reference (Path Y)** — tool recebe `image_id: str` (ex.: `"sample_medical_order.png"`) e resolve internamente.
   - Prós: menor cirurgia no CLI.
   - Contras: apenas move o problema; o modelo continuaria inventando IDs (evidência idêntica); exige contrato externo para o catálogo de IDs.
3. **Registrar hashes alucinados via `register_fixture` (Path Z)** — adicionar os hashes observados ao dict `FIXTURES`.
   - Prós: ~0 trabalho.
   - Contras: hashes são alucinados e mudam por turno/run (confirmado em evidência); viola ADR-0008 (fallback silencioso mascarando defeito); insustentável.
4. **Aguardar primitiva SDK que exponha referência ao `inline_data` dentro de function-call (Path W)** — sem precedente no `google-genai` atual; dívida técnica indefinida.
5. **`before_tool_callback` + `ArtifactService` (Path A — ADK-idiomática)** — a LLM emite `artifact_id: str`; callback intercepta antes da tool executar, carrega o artifact via `tool_context.load_artifact(filename)`, codifica em base64 e reescreve o argumento. Documentado como padrão oficial Google nos codelabs *ADK Multimodal Tool Interaction* Parts 1 e 2 (jan/2026) e na resposta oficial do `adk-bot` no discussion `google/adk-python#2914` ("*The recommended way to manage binary data like images is by using the ADK Artifacts feature*").
   - Prós: idiomático ADK; mantém OCR exposto ao modelo (1 tool inventário); reaproveita `ToolContext`.
   - Contras: (a) introduz `ArtifactService` novo no wiring — hoje só temos `InMemorySessionService`, sem artifact storage; (b) step 1 continua probabilístico (depende da LLM emitir `artifact_id` correto e lembrar de chamar a tool); (c) template Jinja2 do transpilador precisa importar `ToolContext` e `McpTool` para registrar o callback, aumentando o snapshot regerado; (d) unit-testar o step 1 ainda exige LLM no loop. Rejeitada a favor do Path X por **determinismo estrito do step 1** e **delta menor no `generated_agent` e no transpilador** — o avaliador corre um único comando, não há margem para step 1 flaky.

## Decisão

**Adotar Path X (pré-OCR no CLI).** Concretamente:

1. A CLI (`generated_agent/__main__.py`) passa a chamar `extract_exams_from_image` via `mcp.client.sse.sse_client` + `mcp.ClientSession` **antes** de `runner.run_async`. Módulo novo `generated_agent/preocr.py` encapsula o cliente.
2. O `Content` enviado ao runner contém **uma única `Part` de texto** com o prefixo canônico `"EXAMES DETECTADOS (OCR pré-executado pelo CLI): <json-array>"`. Nenhum `inline_data`.
3. O McpToolset do OCR no agente gerado passa a não expor `extract_exams_from_image` ao modelo — via novo campo `exposed: bool = True` em `McpServerSpec` do transpilador (default `true` preserva compat). `spec.example.json` marca OCR como `"exposed": false`.
4. Novos códigos e envs:
   - `E_MCP_UNAVAILABLE` (exit `5`) na taxonomia ADR-0008.
   - `PREOCR_MCP_TIMEOUT_SECONDS` (default `10`), `PREOCR_MCP_CONNECT_RETRIES` (default `1`) em `.env.example` e `docker-compose.yml` service `generated-agent`.
5. **Supersede parcial de ADR-0006** no recorte "tool com argumento derivado de payload binário opaco". Restante de ADR-0006 (topologia LlmAgent único, schema `AgentSpec`, `Literal` de `model` — este também parcialmente superseded por ADR-0009) permanece.

**Princípio generalizável (para specs futuras):** *tool call com payload binário opaco (imagem, áudio, arquivo) é um anti-pattern em LLMs de function-calling atuais; o byte deve ser pré-processado deterministicamente pela CLI e o resultado entrar no prompt como texto estruturado.*

## Consequências

- **Positivas**:
  - Determinismo do passo 1 do plano; fim da dependência de caprichos do modelo sobre bytes.
  - Topologia LlmAgent único preservada; `before_model_callback` de PII continua valendo.
  - Snapshots do transpiler voltam a ser estáveis (sem aleatoriedade derivada de base64 alucinado).
  - OCR-MCP permanece como serviço público testável; apenas deixa de ser exposto ao modelo.
- **Negativas / débito técnico**:
  - CLI ganha responsabilidade orquestradora extra (1 SSE session, 1 tool call) antes do runner.
  - Retry policy do OCR duplica entre server (timeout interno) e CLI (`PREOCR_MCP_CONNECT_RETRIES`). Aceito por simplicidade: CLI executa em ambiente do avaliador, não em serviço.
  - ADR-0006 passa a ter duas supersedências parciais (0009 e 0010); índice `docs/adr/README.md` deixa isso explícito.
- **Impacto em outros subsistemas**:
  - `transpiler/`: `schema.py` e `templates/agent.py.j2` ganham suporte ao flag `exposed`.
  - `generated_agent/`: novo módulo `preocr.py`; refactor de `__main__.py::main` e `_run_agent`.
  - `docs/fixtures/spec.example.json`: OCR server com `"exposed": false` + instruction reescrita.
  - `docs/ARCHITECTURE.md`: fluxo E2E ganha passo 0 (pré-OCR CLI); taxonomia ganha `E_MCP_UNAVAILABLE`.
  - `docs/CONFIGURATION.md` e `.env.example`: novas envs `PREOCR_MCP_*`.
  - `ai-context/references/AGENTIC_PATTERNS.md`: novo verbete *CLI-orchestrated pre-step*.

## Referências

- `docs/specs/0010-pre-ocr-invocation/spec.md`, `plan.md`, `tasks.md`.
- `docs/specs/0009-output-hardening/spec.md § Atualização 2026-04-20`.
- `docs/EVIDENCE/0009-output-hardening.md § Pre-OCR discovery (2026-04-20)` (adicionado em T093 da 0010).
- ADR-0006 (topologia LlmAgent único) — parcialmente superseded por este ADR no recorte de input binário.
- ADR-0001 (MCP transport SSE) — reutilizado pelo cliente MCP da CLI.
- ADR-0003 (PII dupla camada) — Layer 1 continua no OCR-MCP; pré-OCR não altera.
- ADR-0008 (robustez/validação) — novo código `E_MCP_UNAVAILABLE` (exit 5).
- ADR-0009 (config via env) — novas envs `PREOCR_MCP_TIMEOUT_SECONDS` e `PREOCR_MCP_CONNECT_RETRIES`.
- `ai-context/references/AGENTIC_PATTERNS.md § CLI-orchestrated pre-step` (novo verbete).
- https://modelcontextprotocol.io/docs/sdk/python — `mcp.client.sse.sse_client`.
- https://codelabs.developers.google.com/adk-multimodal-tool-part-1 — padrão `before_tool_callback` (Path A, considerado e rejeitado).
- https://codelabs.developers.google.com/adk-multimodal-tool-part-2 — mesmo padrão aplicado a MCP (Path A, considerado e rejeitado).
- https://github.com/google/adk-python/discussions/2914 — resposta oficial `adk-bot` confirmando `ArtifactService` como caminho ADK-idiomático.
