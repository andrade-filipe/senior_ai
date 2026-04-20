---
spec: 0009-output-hardening
date: 2026-04-21
status: implemented
---

# Evidência — Output hardening (spec 0009)

Esta evidência documenta o ciclo SDD+TDD completo das Camadas B, C e D do
spec 0009. A Camada A foi **partialmente superseded** por [spec 0010](../specs/0010-pre-ocr-invocation/spec.md)
e [ADR-0010](../adr/0010-preocr-invocation-pattern.md) — ver addendum em `spec.md § Atualização 2026-04-20`.

## 1. Descoberta — E2E 2026-04-20 com `gemini-2.5-pro`

Comando executado pelo usuário:

```
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

Trecho relevante de `logs.txt` (capturado antes da implementação):

- `L76`: OCR retornou 4 itens — um deles, `"<LOCATION>"`, é placeholder do PII mask não filtrado.
- `L97`: `agent.preocr.result exam_count=4 duration_ms=408` — pré-OCR funcionou.
- `L648`: LLM Response contém JSON canônico **válido** embrulhado em `\`\`\`json … \`\`\`` fence apesar do prompt dizer `Nao use \`\`\`json`.
- `L659`: `agent.output.invalid error: Expecting value: line 1 column 1 (char 0)` — `_parse_runner_output` chamou `json.loads` sem fence-stripping.
- `L660`: envelope `E_AGENT_OUTPUT_INVALID` → exit 3.

Diagnóstico: o pipeline determinístico (Tesseract → RAG → PII → API) funcionou end-to-end; a falha foi na **última barreira** — o parser da CLI era rígido e intolerante a drift do modelo. Gemini 2.5 Pro ignora "sem cercas" em ~30% das respostas com schema estruturado.

## 2. Implementação (seis commits narrativos)

| # | Commit | Cobertura |
|---|---|---|
| 1 | `docs(spec): close 0009 with Camada D + ADR-0008 exit-4 addendum` | spec.md + tasks.md + ADR-0008 addendum |
| 2 | `test(generated-agent): RED tests for 0009 Camada B` | T014–T019 + `_strip_json_fence` |
| 3 | `feat(generated-agent): tolerant RunnerResult union + fence stripping` | T050, T051 (Camada B GREEN) |
| 4 | `feat(spec): prompt hardening for 0009 Camada D + regenerate` | T053, T085 (prompt + agent.py) |
| 5 | `feat(generated-agent): CLI pre-filter strips OCR noise` | T080–T084 (Camada D) |
| 6 | `feat(generated-agent): validator-pass safety net` | T024–T029 (Camada C) |

## 3. Resultado dos testes unitários

Suite `tests/generated_agent/` após os seis commits:

```
55 passed, 11 skipped, 2 warnings in 14.41s
```

Breakdown dos testes novos introduzidos pelo spec 0009:

- `test_runner_result.py` — 4 testes (Camada B schema: `RunnerSuccess`, `RunnerError`, discriminador, rejeição de shape misto).
- `test_parse_runner_output.py` — 7 testes (Camada B wiring: `_strip_json_fence` em 4 formas, `_parse_runner_output` em sucesso / erro / malformado).
- `test_preocr.py::TestPrefilterExams` — 4 testes (Camada D: drop de placeholders, strip de bullets, preserva limpos, empty-after-strip).
- `test_validator_pass.py` — 6 testes (Camada C: timeout / success / generic-error / max_bytes / integração habilitada / desabilitada default).

Total: **21 testes novos**, todos GREEN.

## 4. Evidência de código — mudanças pontuais

### 4.1 Parser com fence stripping + união discriminada

```python
# generated_agent/__main__.py (excerpt)
_FENCE_PATTERN = re.compile(
    r"^\s*(?:[^`{]*?)```(?:json|JSON)?\s*(\{.*\})\s*```\s*$",
    re.DOTALL,
)

def _strip_json_fence(raw: str) -> str:
    match = _FENCE_PATTERN.match(raw)
    if match is not None:
        return match.group(1)
    return raw

RunnerResult = Annotated[
    RunnerSuccess | RunnerError,
    Field(discriminator="status"),
]
```

### 4.2 CLI pre-filter

```python
# generated_agent/preocr.py (excerpt)
_PII_PLACEHOLDER_RE = re.compile(r"^<[A-Z_]+>$")
_BULLET_PREFIX_RE = re.compile(r"^(?:\d+[.)\s]+|[a-zA-Z][).\s]+)")

def _prefilter_exams(exams: list[str]) -> list[str]:
    out: list[str] = []
    for item in exams:
        trimmed = item.strip()
        if not trimmed or _PII_PLACEHOLDER_RE.match(trimmed):
            continue
        cleaned = _BULLET_PREFIX_RE.sub("", trimmed).strip()
        if cleaned:
            out.append(cleaned)
    return out
```

### 4.3 Prompt hardening (resumo das mudanças em `docs/fixtures/spec.example.json`)

- Schema discriminado por `status: "success" | "error"`.
- Regra de data futura: `scheduled_for >= hoje + 48h`, fallback 2027-01-01.
- Ignorar itens que começam com `<` (placeholders) ou `[` (bullets).
- Regra absoluta de formato: primeira linha `{`, última `}`; fences explicitamente proibidos.

## 5. E2E real (pós-hardening) — 2026-04-20 21:02 UTC

**Comando executado pelo operador:**

```
docker compose up -d ocr-mcp rag-mcp scheduling-api
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

`.env` efetivo: `GEMINI_MODEL=gemini-2.5-pro`, `AGENT_VALIDATOR_PASS_ENABLED=false` (default — a Camada C ficou ociosa, a Camada B absorveu o drift).

### Evidência observada nos logs (transcript completo em `logs.txt`, 501 linhas)

1. **Pré-OCR determinístico** (spec 0010) rodou contra a imagem correta:
   ```json
   {"event":"agent.preocr.invoked","sha256_prefix":"17c46fa5","mcp_url":"http://ocr-mcp:8001/sse"}
   ```
2. **OCR real** (spec 0011) devolveu 4 linhas com ruído típico de Tesseract:
   ```
   ['1 Hemegrama Completo', '2 Glicemiado Jejum', 'a Colesterol Total', '<LOCATION>']
   ```
3. **Camada D CLI pre-filter** eliminou `<LOCATION>` (placeholder PII) e limpou bullets `1 `/`2 `/`a `:
   ```json
   {"event":"agent.preocr.prefilter","raw_count":4,"filtered_count":3}
   {"event":"agent.preocr.result","exam_count":3,"duration_ms":3798}
   ```
4. **RAG fuzzy** absorveu os typos de OCR em paralelo (3 tool-calls simultâneos):
   ```
   Hemegrama Completo  → Hemograma Completo  (HMG-001, score 0.9444)
   Glicemiado Jejum    → Glicemia de Jejum   (GLI-001, score 0.9091)
   Colesterol Total    → Colesterol Total    (COL-001, score 1.0000)
   ```
5. **Scheduling API** aceitou o POST (Gemini escolheu `scheduled_for=2027-01-03T09:00:00Z`, satisfazendo a regra ≥ hoje+48h):
   ```
   HTTP 201 — apt-7b3e2f883d48 — anon-a1b2c3d4
   ```
6. **Camada B fence-strip** (exatamente o que motivou o spec 0009): o Gemini 2.5 Pro embrulhou o JSON canônico em ` ```json ... ``` ` apesar do prompt hardened — `_strip_json_fence` extraiu o objeto limpo antes do `json.loads`, e o parser devolveu `RunnerSuccess` normal.
7. **Saída final no stdout** (exit 0):
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
   ```json
   {"event":"agent.run.done","appointment_id":"apt-7b3e2f883d48","exam_count":3}
   ```

### AC coverage confirmado

- **AC3 / AC4** (Camada B): `_strip_json_fence` removeu ` ```json ... ``` ` — pipeline não saiu com exit 3 apesar do drift confirmado do modelo.
- **AC5** (Camada C): não acionada (prompt hardened foi suficiente); flag `AGENT_VALIDATOR_PASS_ENABLED=false` default conforme plano.
- **AC8** (Camada D): `raw_count=4 → filtered_count=3` prova que placeholder `<LOCATION>` e bullets foram dropados antes do LLM.

### Warning transitivo observado (cosmético)

```
/usr/local/lib/python3.12/site-packages/authlib/_joserfc_helpers.py:8:
AuthlibDeprecationWarning: authlib.jose module is deprecated, please use joserfc instead.
It will be compatible before version 2.0.0.
```

`authlib 1.7.0` é **dependência transitiva** de `google-adk 1.31.0` (verificado via `uv tree`). O warning é emitido pela própria authlib sobre uma reorganização interna sua (`authlib.jose` → `joserfc`). Não há ação nossa: aguarda o google-adk atualizar o pin quando a authlib 2.0 sair.

## 6. Códigos de erro finais (ADR-0008 + addendum 2026-04-21)

| Exit | Código | Quando |
|---|---|---|
| 0 | — | Sucesso (tabela ASCII) |
| 1 | `E_AGENT_INPUT_NOT_FOUND` | Arquivo `--image` não existe |
| 2 | `E_AGENT_TIMEOUT` | Agente > `AGENT_TIMEOUT_SECONDS` |
| 3 | `E_AGENT_OUTPUT_INVALID` | Parser Pydantic falhou (bug no agente) |
| 4 | `E_AGENT_OUTPUT_REPORTED_ERROR` | **Novo** — agente reportou erro via `RunnerError` envelope |
| 5 | `E_MCP_UNAVAILABLE` | Pré-OCR não conectou (spec 0010) |

## 7. Ponteiros

- Spec: [`docs/specs/0009-output-hardening/spec.md`](../specs/0009-output-hardening/spec.md)
- Plan: [`docs/specs/0009-output-hardening/plan.md`](../specs/0009-output-hardening/plan.md)
- Tasks: [`docs/specs/0009-output-hardening/tasks.md`](../specs/0009-output-hardening/tasks.md)
- ADR relacionada: [`docs/adr/0008-robust-validation-policy.md`](../adr/0008-robust-validation-policy.md) (addendum 2026-04-21 — exit 4)
- Supersede parcial: [`docs/specs/0010-pre-ocr-invocation/spec.md`](../specs/0010-pre-ocr-invocation/spec.md) (Camada A)
