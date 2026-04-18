---
id: 0006-generated-agent
status: proposed
---

## Abordagem técnica

Este bloco **não escreve código Python manualmente** no `generated_agent/` — o código do agente é **emitido pelo transpilador** (Bloco 2) a partir de um `spec.example.json` (R10). Guardrails de execução do agente (timeout 300 s, validação de output do LLM, cap de `instruction`) conforme [ADR-0008](../../adr/0008-robust-validation-policy.md). O trabalho deste bloco é:

1. Produzir `docs/fixtures/spec.example.json` com `instruction` que incorpora os patterns de [`ai-context/references/AGENTIC_PATTERNS.md`](../../../ai-context/references/AGENTIC_PATTERNS.md) § 2.
2. Produzir `docs/fixtures/sample_medical_order.png` (R10).
3. Ajustar os templates do transpilador (Bloco 2) se necessário para que o `agent.py` gerado satisfaça os ACs — especialmente `before_model_callback` de PII (ADR-0003), `run_config` sem streaming, import de `security.pii_mask`.
4. Escrever uma CLI runner (`scripts/run_agent.py` ou `generated_agent/__main__.py` emitido) que aceite `--image <path>`, leia o arquivo, gere `image_base64`, invoque `adk run`, e imprima a tabela final.
5. Testes de integração com serviços reais (MCPs + API) up no compose.

Topologia do agente: **LlmAgent único** ([ADR-0006](../../adr/0006-spec-schema-and-agent-topology.md)). Tools: duas via `McpToolset(connection_params=StreamableHTTPConnectionParams(...))` + uma via OpenAPI toolset do ADK para `scheduling-api`. Callback: `before_model_callback = make_pii_callback(guardrails.pii.allow_list)` importado de `security` (ADR-0003).

### Instruction (incorpora patterns)

Esboço para o `spec.example.json` — linguagem imperativa em PT-BR, forma final fica em RED:

```
Você é um agente de agendamento de exames médicos.

Plano fixo (plan-then-execute):
 1. Chame extract_exams_from_image(image_base64) UMA vez para obter a lista completa de exames.
 2. Para cada exame retornado, chame search_exam_code em PARALELO (múltiplas tool calls na mesma resposta).
 3. Monte uma lista interna [(nome, código, score, correlation_id)] — NÃO formate a tabela ainda.
 4. Se alguma busca retornar null, chame list_exams(limit=5) e marque aquele exame como "não-conclusivo".
 5. Faça UM ÚNICO POST /api/v1/appointments com todos os exames no campo exams[].
 6. SÓ ENTÃO formate a tabela final no terminal, citando origem e score (trustworthy generation).

Política de erro (congelada):
 - E_MCP_TIMEOUT: **1 retry, delay fixo de 500 ms**; se persistir, propague `ChallengeError` com `hint="Verifique se os serviços MCP estão saudáveis (docker compose ps)"` e aborte.
 - E_RAG_NO_MATCH (score < 0.80 ou retorno `None` do `search_exam_code`): **zero retry**. Chame `list_exams(limit=20)` e apresente top candidatos ao usuário pedindo confirmação/correção antes de continuar. Marque o exame como "não-conclusivo".
 - E_API_VALIDATION (422 do `scheduling-api`): **zero retry** — retry causaria agendamento duplicado (write-action não idempotente). Reporte ao usuário o `<campo>` + `<motivo>` extraído da mensagem Pydantic.

Restrições:
 - NUNCA inclua nomes, CPFs ou telefones no texto final. Use <PERSON>, <CPF> etc. conforme recebidos.
 - patient_ref é SEMPRE anon-<hash>. Nunca invente.
```

### Runner CLI

Função canônica emitida pelo template:

```python
# generated_agent/__main__.py (gerado)
def main() -> int:
    args = parse_args()             # --image, --spec
    image_base64 = b64encode(open(args.image, "rb").read()).decode()
    runner = Runner(root_agent)
    result = asyncio.run(runner.run_async(prompt=image_base64))
    print_final_table(result)
    return 0
```

### Fixtures

- `docs/fixtures/sample_medical_order.png` — imagem do pedido médico **gerada via Pillow** (Bloco 3 T002) com cabeçalho "Pedido Médico" + 3 a 5 nomes de exames do catálogo RAG + nome fake + CPF fake. É fixture commitada (não gerada em runtime); hash fixo reutilizado em `ocr_mcp/fixtures.py`.
- `docs/fixtures/spec.example.json` — schema do Bloco 1, com os três blocos (OCR, RAG, scheduling) cabeados e `instruction` acima.
- Hash de `sample_medical_order.png` adicionado em `ocr_mcp/fixtures.py` (Bloco 3) para que o OCR mock retorne exames canônicos.

## Data models

Consome modelos dos Blocos 1, 3, 4, 5:
- `AgentSpec` (para construir o `spec.example.json`).
- `ExamMatch`, `ExamSummary` (saídas do RAG).
- `AppointmentCreate`, `Appointment` (API).
- `MaskedResult` (via callback).

Modelo local (agregador interno do agente):

```python
@dataclass
class ExamResolution:
    raw_name: str          # saída do OCR (já mascarado)
    match: ExamMatch | None
    inconclusive: bool     # True quando score < 0.80 ou degraded mode
```

## Contratos

Consome:
- OCR/RAG MCP via SSE ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Contratos entre subsistemas").
- Scheduling API via OpenAPI ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Agente → Scheduling API").
- `security.pii_mask` (Bloco 5).

Não introduz contratos novos — usa os que já foram definidos.

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `root_agent` | pacote `generated_agent/` emitido pelo transpilador (Bloco 2) | `LlmAgent` válido com tools cabeadas | `before_model_callback` registrado e aponta para `security.pii_mask` (ADR-0003) — nenhuma chamada ao LLM sem mascaramento prévio; logs nunca carregam PII (ADR-0008) | AC4, AC21 | T013 `[DbC]`, T029 `[DbC]` |
| Retry policy (contrato textual no `instruction`) | erro de tool classificado em `E_MCP_TIMEOUT` / `E_RAG_NO_MATCH` / `E_API_VALIDATION` | política aplicada: 1 retry (MCP), 0 retry (RAG, API) | `E_API_VALIDATION` **nunca** retenta — evita agendamento duplicado (write-action não-idempotente) | AC14, AC15, AC16 | T023 `[DbC]`, T024 `[DbC]`, T025 `[DbC]` |
| Runner CLI (`generated_agent/__main__.py`) | env vars válidas; imagem existe | imprime tabela + appointment ID em < 300 s (ADR-0008) | timeout 300 s → `E_AGENT_TIMEOUT`; output malformado do LLM → `E_AGENT_OUTPUT_INVALID` (zero retry) | AC18, AC19 | T027 `[DbC]`, T028 `[DbC]` |
| `AgentSpec.instruction` | ≤ 4096 bytes UTF-8 (ADR-0008) | validada pelo Bloco 1 antes de render | cap enforced pelo `transpiler.load_spec` | AC20 | T031 `[DbC]` |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `google-adk` | pinado exato (ver nota) | ADK runtime (ADR-0005) | — |
| `mcp[cli]` | `^1.0` | Cliente MCP (consumo) | — |
| `security` | local | PII callback (ADR-0003) | — |
| `httpx` ou OpenAPI toolset do ADK | — | Tool da API | Adapter manual (fallback se ADK OpenAPI toolset tiver bug) |

Nota: pin exato de `google-adk` fica no `requirements.txt` gerado; ADR-0005 já prevê que mudança de versão exige nota/ADR.

## Riscos

| Risco | Mitigação |
|---|---|
| ADK pode serializar tool calls mesmo com múltiplas requisições — quebra AC2 (paralelismo). | Medir em E2E. Se ADK serializa, degradar AC2 para "todas as chamadas saem antes do POST" (não exige paralelo duro); fica em nota de evidência + ADR se precisar mudar spec. |
| `before_model_callback` requer acesso a `llm_request.contents[].parts[].text` — assinatura do ADK pode variar. | Seguir docs oficiais (ADR-0003 nota: confirmado em `adk.dev/callbacks/`). Teste isolado do callback antes do integration. |
| Gemini pode alucinar e preencher campos PII mesmo com guard. | `after_model_callback` com re-mask também pode ser adicionado (já previsto em ADR-0003 como "opcional"); decide-se em review. |
| `spec.example.json` fica obsoleto se algum contrato mudar. | Validar no CI que `spec.example.json` passa `transpiler.load_spec` (Bloco 1) como parte do smoke do transpilador. |
| Runner CLI (o `__main__` gerado) precisa de `GOOGLE_API_KEY` — E2E real exige segredo. | CI roda apenas E2E leve (compose + healthchecks + unit/integration sem chamada Gemini real — Bloco 8 AC1a); E2E completo com Gemini é manual, documentado no README (Bloco 8 AC1b). Local usa `.env` não commitado. |

## Estratégia de validação

- **Same-commit** (ADR-0004) — `generated_agent/` não é módulo de test-first obrigatório.
- **Unit** do callback PII: isolado, mockando `llm_request` com prompt sintético contendo PII, esperando texto mascarado (AC4).
- **Integration** (require `docker compose` subset): sobe `ocr-mcp`, `rag-mcp`, `scheduling-api`, roda o agente contra `sample_medical_order.png`. Valida AC1, AC3, AC5, AC6, AC7, AC8, AC9, AC10, AC11, AC12.
- **AC2 (paralelismo)**: log-based — dentro de uma janela < 100 ms, N chamadas a `search_exam_code` são registradas. Se ADK não paraleliza, documentar em evidência e relaxar AC2 via ADR.
- **Fixture smoke** (AC13): `test_fixtures.py` valida existência e parseabilidade de `sample_medical_order.png` e `spec.example.json`.
- **PII regression**: teste E2E inspeciona o corpo do POST capturado e o conteúdo da chamada ao Gemini (via hook de teste) — nenhum valor PII cru.
- **Cobertura**: reportada em evidência; não é gate para `generated_agent/` porque o código é **gerado** e coberto indiretamente pelos testes do Bloco 2 + este bloco.

**Estratégia de validação atualizada (ADR-0008)**:
- **Agent timeout (AC18)**: runner CLI envolve `asyncio.run(runner.run_async(...))` em `asyncio.wait_for(..., timeout=300.0)`; timeout → `ChallengeError(code="E_AGENT_TIMEOUT")` impresso no stderr via `format_challenge_error`.
- **Agent output validation (AC19)**: runner valida output final contra Pydantic model interno (`ExamResolution[]` + appointment confirmado); validação falha → `ChallengeError(code="E_AGENT_OUTPUT_INVALID")`.
- **`instruction` cap (AC20)**: reforço no Bloco 1 — `AgentSpec.instruction: str = Field(max_length=4096)`; teste em `tests/generated_agent/test_spec_example.py` valida que a `instruction` real do `spec.example.json` está abaixo do cap.
- **No-PII-in-logs (AC21)**: runner e callbacks emitem logs apenas com `params_hash`, `sha256_prefix`, contadores; teste `caplog` valida via regex PII de ARCHITECTURE.

## Dependências entre blocos

- **Depende, em código**, de:
  - Bloco 2 (transpilador) — precisa do generator funcionando para emitir o pacote.
  - Bloco 3 (OCR/RAG) — precisa dos serviços up para integration.
  - Bloco 4 (scheduling-api) — precisa da API up para integration.
  - Bloco 5 (security) — precisa do `pii_mask` importável.
- Em termos de **spec/contrato**: **independente** — todos os contratos estão congelados em ADRs + ARCHITECTURE. Engenheiros de Blocos 3/4/5 podem trabalhar em paralelo com este durante a fase RED (`qa-engineer` escreve os testes deste bloco sem precisar dos serviços up).
- **Bloqueia** Bloco 8 (E2E depende de ter um agente funcional).
