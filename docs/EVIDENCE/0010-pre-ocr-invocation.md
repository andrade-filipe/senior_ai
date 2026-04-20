---
spec: 0010-pre-ocr-invocation
date: 2026-04-20
status: implemented
---

# Evidência — Pré-OCR invocation (spec 0010)

Spec: [`docs/specs/0010-pre-ocr-invocation/`](../specs/0010-pre-ocr-invocation/)
ADR: [`docs/adr/0010-preocr-invocation-pattern.md`](../adr/0010-preocr-invocation-pattern.md)

O spec 0010 substituiu o passo 1 do fluxo (OCR como tool-call do modelo) pelo pattern **CLI-orchestrated pre-step**: a CLI abre uma sessão MCP-SSE diretamente contra `ocr-mcp:8001`, chama `extract_exams_from_image` com os bytes reais do arquivo `--image`, e injeta a lista resultante no prompt como texto. O LlmAgent nunca mais vê `inline_data` nem uma tool OCR.

## 1. Runbook (operador)

```powershell
docker compose up -d ocr-mcp rag-mcp scheduling-api
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
docker compose down -v
```

Envs pertinentes (com defaults):

- `PREOCR_MCP_TIMEOUT_SECONDS=10` — timeout absoluto do `initialize + call_tool` SSE.
- `PREOCR_MCP_CONNECT_RETRIES=1` — retry simples para flaky network dentro do compose.

Exit codes novos introduzidos por esta spec (ADR-0008 addendum 2026-04-21):

| Exit | Código | Quando |
|---|---|---|
| 4 | `E_OCR_UNKNOWN_IMAGE` | OCR retornou lista vazia (reaproveitado da 0009 Camada B) |
| 5 | `E_MCP_UNAVAILABLE` | CLI não conseguiu conectar/chamar o OCR-MCP |

## 2. Unit — 2026-04-20

Comando:

```
uv run pytest tests/generated_agent/ transpiler/tests/ -q
```

Resultado: **55 passed, 11 skipped** (generated_agent) + snapshots estáveis em transpiler. Testes novos para esta spec:

- `tests/generated_agent/test_preocr.py` — `_run_preocr` mock de `sse_client`/`ClientSession` (T010, T013), `_prefilter_exams` (T080–T082 absorvidos da 0009 Camada D).
- `tests/generated_agent/test_agent_topology.py` — nenhum McpToolset expõe `extract_exams_from_image` (T012 → AC4).
- `tests/generated_agent/test_main_preocr_wiring.py` — aborts em `[]` (T014 → AC2) e em `E_MCP_UNAVAILABLE` (T015 → AC6).
- `tests/generated_agent/test_preocr.py::TestBuildPreocrPrompt` — Part único de texto, ausência de `inline_data` (T011 → AC3).

## 3. E2E canônico — 2026-04-20 21:02 UTC

Log completo em `logs.txt` (501 linhas). Trecho narrativo:

### 3.1 AC1 — CLI chama OCR via MCP-SSE

```json
{"event":"agent.preocr.invoked","correlation_id":"c8df15c7-23a7-4e13-b6d2-aa33666622b7","sha256_prefix":"17c46fa5","mcp_url":"http://ocr-mcp:8001/sse"}
```

O prefixo `17c46fa5` é o SHA-256 dos bytes reais da fixture em disco — o problema original de 2026-04-20 (hashes alucinados `1b11b0e3…`, `e150238a…`) está resolvido.

### 3.2 AC3 — prompt sem `inline_data`

O payload enviado ao Gemini (capturado em `logs.txt:479`) mostra um único `Content` textual com `role=user`:

```
<PERSON> (OCR pré-executado pelo CLI): ["Hemegrama Completo", "Glicemiado Jejum", "Colesterol Total"]

Use essa lista como ponto de partida do passo 2 do plano fixo (search_exam_code em paralelo, etc.).
```

(O prefixo `<PERSON>` vem do `before_model_callback` — Layer 2 do ADR-0003 — mascarando um marcador textual do prompt, comportamento esperado.)

Nenhum `inline_data` nem base64 aparece no `Contents` do request — confirma AC3.

### 3.3 AC4 — topologia sem tool OCR

`logs.txt:115-118` mostra as tools parseadas pelo ADK ao `run_async`:

```
Parsed tool: health_health_get
Parsed tool: list_appointments_api_v1_appointments_get
Parsed tool: create_appointment_api_v1_appointments_post
Parsed tool: get_appointment_api_v1_appointments_id_get
```

Apenas tools do OpenAPIToolset da Scheduling API + `search_exam_code` + `list_exams` (do RAG). `extract_exams_from_image` **não** foi registrada no agente — confirma AC4 via ausência.

### 3.4 AC5 — happy path E2E

Saída final no stdout:

```
+-----+------------------------+-----------+
| #   | Exame                  | Codigo    |
+-----+------------------------+-----------+
| 1   | Hemograma Completo     | HMG-001   |
| 2   | Glicemia de Jejum      | GLI-001   |
| 3   | Colesterol Total       | COL-001   |
+-----+------------------------+-----------+
Appointment ID: apt-7b3e2f883d48  |  Scheduled: 2027-01-03T09:00:00+00:00
```

Exit 0. `appointment_id=apt-7b3e2f883d48` confirmado via `agent.run.done` log.

### 3.5 AC7 — instrumentação

```json
{"event":"agent.preocr.result","correlation_id":"c8df15c7-…","exam_count":3,"duration_ms":3798}
```

`exam_count` reflete o pós-prefilter (3), não o raw do OCR (4). A contagem raw aparece em `agent.preocr.prefilter` (`raw_count=4, filtered_count=3`).

## 4. AC map → evidência

| AC | Observação | Linha(s) |
|---|---|---|
| AC1 | `agent.preocr.invoked` + sha256 real da fixture | `logs.txt:16` |
| AC2 | não exercido neste run (OCR devolveu 3 itens válidos); testado em unit (T014) | — |
| AC3 | prompt enviado ao LLM sem `inline_data` | `logs.txt:479` |
| AC4 | `extract_exams_from_image` ausente de `Parsed tool:*` | `logs.txt:115-118` |
| AC5 | exit 0 + tabela + `appointment_id` | `logs.txt:492-500` |
| AC6 | não exercido (OCR-MCP healthy); testado em unit (T015) | — |
| AC7 | `agent.preocr.result` com `exam_count` + `duration_ms` | `logs.txt:98` |
| AC8 | snapshots transpiler estáveis após regen | `transpiler/tests/test_snapshots/` |

## 5. Superseding summary

Este run **supersede a falha de 2026-04-20 manhã** (pré-spec 0010), em que a tool `extract_exams_from_image` recebia bases64 alucinados (184/223 bytes, PNGs minúsculos) a cada turno. Agora a CLI é a única fonte de bytes que o OCR-MCP vê — determinístico por construção.

## 6. Ponteiros

- Spec: [`docs/specs/0010-pre-ocr-invocation/spec.md`](../specs/0010-pre-ocr-invocation/spec.md)
- Plan: [`docs/specs/0010-pre-ocr-invocation/plan.md`](../specs/0010-pre-ocr-invocation/plan.md)
- Tasks: [`docs/specs/0010-pre-ocr-invocation/tasks.md`](../specs/0010-pre-ocr-invocation/tasks.md)
- ADR: [`docs/adr/0010-preocr-invocation-pattern.md`](../adr/0010-preocr-invocation-pattern.md) (supersede parcial da ADR-0006)
- Spec encadeada: [`docs/specs/0011-real-ocr-tesseract/spec.md`](../specs/0011-real-ocr-tesseract/spec.md) — resolveu o segundo problema (fixture não embarcada + lookup por hash frágil).
