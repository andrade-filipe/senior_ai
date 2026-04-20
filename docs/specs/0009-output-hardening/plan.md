---
id: 0009-output-hardening
status: approved
---

> **Nota 2026-04-20**: a **Camada A** deste plano (fixture reliability via `register_fixture` + log `ocr.lookup.hash`) foi **partialmente superseded** por [spec 0010 `pre-ocr-invocation`](../0010-pre-ocr-invocation/plan.md) e [ADR-0010](../../adr/0010-preocr-invocation-pattern.md). A causa raiz descoberta pelo log T041 é arquitetural (Gemini não reencaminha bytes de `inline_data` como arg de tool); a correção passou para o nível da CLI. **Camadas B e C deste plano permanecem válidas e ativas.** Ver addendum em `spec.md § Atualização 2026-04-20`.

## Abordagem técnica

Três camadas ortogonais, atacadas na ordem A → B → C. Cada uma **sozinha** melhora a entrega; juntas dão E2E robusto.

- **Camada A — Fixture reliability (root-cause de AC1, AC2)**. Instrumentar o tool OCR para logar o sha256 **do payload que o modelo efetivamente envia** (não do arquivo em disco). Validar se o hash diverge do registrado; se sim, adicionar o hash observado ao `FIXTURES` dict. Expor `register_fixture(image_path, exams)` para registro explícito por testes. **Não** introduz lookup perceptual.
- **Camada B — Tolerant RunnerOutput (AC3, AC4)**. Substituir `_RunnerOutput` por união discriminada `RunnerResult = RunnerSuccess | RunnerError`. Atualizar o prompt fixo do agente (via `spec.example.json`) para documentar o envelope de erro canônico. Regenerar agent.py. Diferenciar exit codes: `0`=sucesso, `3`=parser malformado, `4`=erro reportado pelo agente.
- **Camada C — Validator-pass opcional (AC5, AC6, AC7)**. Nova função `_run_validator_pass(raw_text, correlation_id)` em `generated_agent/validator.py`. Chama `google.genai` direto (sem ADK, sem tools) com `response_json_schema = RunnerResult.model_json_schema()`. Prompt hardcoded: "Reformate o texto a seguir para este schema JSON. Sem markdown." Retorno válido entra no parser Pydantic; falha cai no comportamento atual. Feature flag `AGENT_VALIDATOR_PASS_ENABLED=false` default. Sempre aplicada **só quando o parser primário falha** — nunca no happy path.

Padrões de referência:
- [`AGENTIC_PATTERNS.md § assembled reformat`](../../../ai-context/references/AGENTIC_PATTERNS.md) — pipeline determinístico pós-LLM.
- ADR-0009 — toda feature nova é env-configurável.
- ADR-0003 — PII já foi aplicada pelo agente principal; validator não precisa de `before_model_callback` próprio.

## Data models

```python
# generated_agent/__main__.py (substitui _RunnerOutput atual)

class ExamResolution(BaseModel):
    name: str
    code: str
    score: float = Field(ge=0.0, le=1.0)
    inconclusive: bool = False

class RunnerSuccess(BaseModel):
    status: Literal["success"] = "success"
    exams: list[ExamResolution]
    appointment_id: str
    scheduled_for: datetime

class RunnerErrorDetail(BaseModel):
    code: str                      # E_OCR_UNKNOWN_IMAGE, E_API_VALIDATION, etc.
    message: str
    hint: str | None = None

class RunnerError(BaseModel):
    status: Literal["error"] = "error"
    error: RunnerErrorDetail

RunnerResult = Annotated[
    RunnerSuccess | RunnerError,
    Field(discriminator="status"),
]
```

Discriminador `status` é obrigatório no JSON — evita ambiguidade quando ambas as formas têm campos opcionais coincidentes.

Exemplo canônico de sucesso (inalterado em shape, novo campo `status`):
```json
{
  "status": "success",
  "exams": [{"name": "Hemograma Completo", "code": "HEMO", "score": 0.92, "inconclusive": false}],
  "appointment_id": "appt-42",
  "scheduled_for": "2026-04-21T09:00:00-03:00"
}
```

Exemplo canônico de erro:
```json
{
  "status": "error",
  "error": {
    "code": "E_OCR_UNKNOWN_IMAGE",
    "message": "OCR nao reconheceu a imagem fornecida (hash nao registrado).",
    "hint": "Registre a fixture com register_fixture(path, exams)."
  }
}
```

## Contratos

### OCR tool (atualizado)

`extract_exams_from_image(image_base64: str) -> list[str]` — assinatura inalterada. **Muda**: log estruturado adicional `ocr.lookup.hash` com o digest do payload decodificado para facilitar debug de divergência.

### `_parse_runner_output(raw, correlation_id) -> RunnerResult`

- Tenta `RunnerResult.model_validate(data)` diretamente (union com discriminador).
- Se `pydantic.ValidationError`:
  - Se `AGENT_VALIDATOR_PASS_ENABLED`: tenta `_run_validator_pass(text, correlation_id)`; valida resultado reformatado.
  - Se ainda falha: `_exit_error(E_AGENT_OUTPUT_INVALID, exit_code=3)`.
- Se `RunnerError`: `_exit_error(E_AGENT_OUTPUT_REPORTED_ERROR, exit_code=4)` com o conteúdo do envelope.
- Se `RunnerSuccess`: retorna para o pipeline de formatação atual.

### `_run_validator_pass(raw_text: str, correlation_id: str) -> str | None`

- Pre: `raw_text` é string não vazia, `len(raw_text) ≤ VALIDATOR_MAX_INPUT_BYTES`.
- Post: retorna string JSON que satisfaz `RunnerResult` (conteudalmente, não validado aqui), ou `None` em qualquer falha (timeout, HTTP, JSON inválido, schema não satisfeito).
- Invariant: **nunca lança exceção ao caller**; falha sempre vira `None`.

### Prompt do validator (hardcoded)

```
Voce e um reformatador estrutural. Dado o texto a seguir, devolva UM UNICO objeto JSON
que satisfaz o schema abaixo. Nao invente campos. Se o texto descreve sucesso, use
status="success"; se descreve falha, use status="error". Nao use markdown nem fences.
Nao adicione texto antes ou depois.

SCHEMA:
<json-schema-aqui>

TEXTO:
<raw-aqui>
```

## Design by Contract

| Alvo | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `ocr_mcp.fixtures.register_fixture` | `image_path` existe; `exams: list[str]` não vazio | `FIXTURES[sha256(bytes)] == exams` | registros prévios preservados | AC2 | T020 [DbC] |
| `ocr_mcp.fixtures.lookup` | `image_base64` é base64 RFC 4648 válido | retorna `FIXTURES.get(digest, [])` | nunca levanta em input válido | AC1 | T021 [DbC] |
| `RunnerResult` | JSON tem campo `status ∈ {"success","error"}` | instância discriminada correta | shape imutável pós-`model_validate` | AC3, AC4 | T022 [DbC] |
| `_parse_runner_output` | `raw` é Event/dict/str; `correlation_id` UUID | `RunnerResult` válido OU `sys.exit(3|4)` | nunca retorna dict cru | AC3, AC4 | T023 [DbC] |
| `_run_validator_pass` | `raw_text` não vazio, ≤ cap | retorna JSON string válido ou `None` | nunca levanta; timeout respeitado | AC5, AC7 | T024 [DbC] |

**Onde declarar no código**:
- Docstrings Google-style com seções `Pre`, `Post`, `Invariant` em cada função da tabela.
- Pydantic validators para o schema.
- `assert` em entradas de `_run_validator_pass` para Pre.

**Onde enforcar**:
- Cada linha tem teste marcado `[DbC]` em `tasks.md § Tests`.
- `code-reviewer` checa trace triplo AC ↔ DbC ↔ test.

## Dependências

Nenhuma lib nova. Usa o que já existe:
- `google-genai` (transitive via `google-adk`) — `google.genai.Client` direto para validator-pass.
- `pydantic` — `Field(discriminator=...)` já suportado na v2.

## Riscos

- **R1 — Hipótese de re-encode Gemini errada**. Se o teste dirigido em Q1 mostrar que o hash bate, então OCR devolvendo `[]` tem outra causa (ex.: o argumento da tool chegou vazio por token limit, ou cortado). Mitigação: log `ocr.lookup.hash` + `ocr.lookup.payload_size` desambigua em 1 rodada.
- **R2 — Validator-pass mascara regressões silenciosas**. Mitigação: default `false`; log `agent.validator.applied` com diff dos hashes; teste E2E happy-path roda com flag desligada (AC3, AC8).
- **R3 — Gemini API do validator também 503**. Mitigação: AC7 garante fallback silencioso; E2E continua com exit 3, que já era o comportamento anterior.
- **R4 — Union discriminada quebra snapshots do transpiler**. Mitigação: T3 regenera snapshots no mesmo commit que muda schema.
- **R5 — Exit code 4 novo não é documentado em ADR-0008**. Mitigação: addendum curto no `docs/adr/0008-robust-validation-policy.md` anexando a nova classe de erro (não supersede; amplia).

## Estratégia de validação

- **Unitário**:
  - `ocr_mcp/tests/test_fixtures_roundtrip.py` — base64 do PNG canônico → `lookup()` devolve a lista.
  - `ocr_mcp/tests/test_register_fixture.py` — `register_fixture` popula dict corretamente; duplicatas atualizam.
  - `tests/generated_agent/test_runner_result.py` — valida RunnerSuccess, RunnerError, schemas mistos rejeitados pela união.
  - `tests/generated_agent/test_validator_pass.py` — mock `google.genai.Client.generate_content`; valida caminhos happy/timeout/schema-miss.
- **Integração**:
  - `tests/generated_agent/test_parse_runner_output.py` — inputs canônicos + drift (fences, prosa, schema errado) → `RunnerResult` ou `SystemExit` com código esperado.
- **E2E**:
  - `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` → exit 0, stdout com tabela ASCII.
  - Captura em `docs/EVIDENCE/0009-output-hardening.md`.
- **Inspeção manual**:
  - Verificar que `code-reviewer` aprova o trace AC ↔ DbC ↔ Task ↔ Test.
  - Verificar que a mudança de prompt no `spec.example.json` propaga corretamente via `uv run transpile` e o snapshot do transpiler bate.
