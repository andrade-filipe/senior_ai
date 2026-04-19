# Evidência — Bloco 0006: Agente ADK end-to-end

**Status**: estrutura de design + smoke validados pelos testes unitários (53 transpiler + 73 security + 28 generated_agent pass; mypy limpo). Execução E2E com Gemini real é manual (T021 do Bloco 0008 — propriedade do avaliador/usuário) e segue o runbook consolidado abaixo, idêntico ao de [`docs/EVIDENCE/0008-e2e-evidence-transparency.md`](./0008-e2e-evidence-transparency.md) (AC1b).

Commits relevantes: `c2836a9` (round 1) + 5 commits individuais do round 2 (ver `ai-context/STATUS.md` § histórico 2026-04-19 para detalhe dos blockers e fixes).

---

## AC1b — Runbook de E2E Manual

> Este roteiro é executado localmente pelo avaliador. Requer `GOOGLE_API_KEY` válida. Saída real do Gemini será anexada pelo usuário após a rodada (T021 do Bloco 0008).

```bash
# 1. Clonar e configurar
git clone <repo-url>
cd Senior_IA
cp .env.example .env
# Editar .env: preencher GOOGLE_API_KEY=AIza...

# 2. Subir stack (3 serviços de infraestrutura)
docker compose up -d ocr-mcp rag-mcp scheduling-api

# 3. Aguardar healthchecks (até 60s)
docker compose ps

# 4. Executar agente com imagem de exemplo
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png

# 5. Verificar resultado esperado:
# - Saída tabela ASCII no terminal (seção "Tabela final")
# - POST criado na API: http://localhost:8000/api/v1/appointments
# - Log com correlation_id visível em: docker compose logs scheduling-api

# 6. Teardown
docker compose down -v
```

---

## Forma esperada da saída (será preenchida pelo avaliador após T021)

> *Saída a ser preenchida pelo avaliador após rodar o fluxo; exemplo de forma esperada abaixo.* A sequência de tool-calls esperada, conforme `instruction` do `spec.example.json`, é **OCR → RAG (1 call por exame) → schedule_appointment** (uma única chamada `POST /api/v1/appointments` ao final).

### Sequência de `event=tool.called` no log

Exemplo da forma esperada (pelo menos 5 entradas: 1× OCR + 3× RAG + 1× schedule):

```json
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "extract_exams_from_image", "params_hash": "aabbccdd11223344", "duration_ms": 120.5, "correlation_id": "f47ac10b-..."}
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "params_hash": "11223344aabbccdd", "duration_ms": 45.2, "correlation_id": "f47ac10b-..."}
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "params_hash": "22334455bbccddee", "duration_ms": 42.8, "correlation_id": "f47ac10b-..."}
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "params_hash": "33445566ccddeeff", "duration_ms": 41.1, "correlation_id": "f47ac10b-..."}
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "schedule_appointment", "params_hash": "44556677ddeeff00", "duration_ms": 18.3, "correlation_id": "f47ac10b-..."}
```

Todas as 5 entradas devem compartilhar o **mesmo `correlation_id`** — prova de que a propagação de contexto via `X-Correlation-ID` funcionou ponta a ponta.

### POST body capturado — sem PII

Forma esperada do corpo da requisição `POST /api/v1/appointments` (capturado via log do `scheduling-api`):

```json
{
  "patient_ref": "anon-a1b2c3d4",
  "exams": [
    {"name": "Hemograma Completo", "code": "HMG-001"},
    {"name": "Glicemia de Jejum", "code": "GLJ-002"},
    {"name": "Colesterol Total", "code": "COL-003"}
  ],
  "scheduled_for": "2026-05-01T09:00:00Z",
  "notes": null
}
```

`patient_ref=anon-<hash>` confirma que o PII Guard (Layer 1 no OCR MCP + Layer 2 no `before_model_callback` do ADK — ADR-0003) removeu qualquer nome, CPF, telefone ou e-mail antes da requisição sair do processo do agente.

### Tabela final no terminal

Forma esperada do output ASCII impresso ao final da execução:

```
+-----+--------------------+---------+-------+
| #   | Exame              | Codigo  | Score |
+-----+--------------------+---------+-------+
| 1   | Hemograma Completo | HMG-001 | 0.98  |
| 2   | Glicemia de Jejum  | GLJ-002 | 0.96  |
| 3   | Colesterol Total   | COL-003 | 0.94  |
+-----+--------------------+---------+-------+
Appointment ID: apt-abc123  |  Scheduled: 2026-05-01T09:00:00
```

---

## Saída real do Gemini (placeholder — T021)

> *Saída a ser preenchida pelo avaliador após rodar o fluxo completo com `GOOGLE_API_KEY` válida.* O usuário anexa aqui a transcrição literal do stdout/stderr do container `generated-agent` (linhas de log JSON + tabela ASCII final) e a resposta `201 Created` da `scheduling-api` contendo o `id` retornado. Real Gemini output will be appended by the user in T021.

---

## Cobertura de testes relacionados

| Teste | Arquivo | Cobre |
|---|---|---|
| `test_run_agent_closes_toolsets_on_timeout` | `generated_agent/tests/test_main.py` | Cancelamento real via `wait_for(0.1)` + verificação de `close()` nos dois toolsets no `finally`. |
| `test_before_model_callback_masks_pii` | `security/tests/test_callbacks.py` | Layer 2 do ADR-0003 acoplada ao `before_model_callback` do ADK. |
| `test_correlation_id_propagated_on_outgoing_http` | `generated_agent/tests/test_main.py` | `X-Correlation-ID` sai em toda chamada HTTP de saída. |
| `test_spec_example_passes_transpiler_load_spec` | `tests/infra/test_fixtures.py` | `docs/fixtures/spec.example.json` valida contra o schema Pydantic. |

Testes `@skip_integration` (11) permanecem marcados e rodam somente com o compose de pé — exercitados pela suíte E2E do Bloco 0008.
