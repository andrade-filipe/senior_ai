---
id: 0010-pre-ocr-invocation
status: done
---

## Abordagem técnica

Pré-OCR determinístico no CLI. A CLI chama o OCR-MCP diretamente via cliente SSE (`mcp.client.sse.sse_client` + `mcp.ClientSession`), recebe `list[str]` de exames e injeta-os como **texto** no prompt do `LlmAgent`. O passo 1 do plano fixo ("chame extract_exams_from_image") sai; entra um prefixo canônico `"EXAMES DETECTADOS (OCR pré-executado pelo CLI): <json-array>"`. O `LlmAgent` continua único (ADR-0006 topologia preservada); o que muda é apenas a fonte do primeiro dado.

Padrões de referência:
- [`AGENTIC_PATTERNS.md § CLI-orchestrated pre-step`](../../../ai-context/references/AGENTIC_PATTERNS.md) — novo verbete introduzido por esta spec.
- ADR-0010 — pattern arquitetural; supersede parcial de ADR-0006 no ponto "tool call com argumento binário".
- ADR-0001 — MCP transport SSE (inalterado); reutilizado pela CLI.
- ADR-0003 — PII Layer 1 aplicada pelo OCR-MCP continua valendo; lista chega já mascarada à CLI.
- ADR-0008 — novo código `E_MCP_UNAVAILABLE` (exit 5) na taxonomia.
- ADR-0009 — envs `PREOCR_MCP_TIMEOUT_SECONDS` e `PREOCR_MCP_CONNECT_RETRIES` em `.env.example` + compose.

## Data models

Nenhum schema Pydantic novo. `AgentSpec` ganha campo opcional `exposed: bool = True` em `McpServerSpec` (permite marcar um server como não-exposto ao modelo, mantendo-o disponível no server para uso direto):

```python
# transpiler/transpiler/schema.py (adição)

class McpServerSpec(BaseModel):
    name: str
    url: str
    tool_filter: list[str] | None = None
    exposed: bool = True   # NOVO — False => McpToolset com tool_filter=[]
```

Fixture `docs/fixtures/spec.example.json` ganha `"exposed": false` no OCR server e tem a `instruction` reescrita.

## Contratos

### Novo módulo `generated_agent/preocr.py`

```python
class _PreOcrError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None) -> None: ...
    code: str
    message: str
    hint: str | None

async def _run_preocr(
    image_bytes: bytes,
    correlation_id: str,
    *,
    mcp_url: str,
    timeout_s: float,
    connect_retries: int = 1,
) -> list[str]:
    """Invoca extract_exams_from_image via MCP-SSE e retorna a lista.

    Pre:
        image_bytes não vazio; mcp_url é URL SSE válida (começa com http/https).

    Post:
        retorna list[str] (possivelmente vazia) OU levanta _PreOcrError com
        {code, message, hint} mapeados para a taxonomia ADR-0008.

    Invariant:
        timeout absoluto respeitado (sse_client + initialize + call_tool);
        PII Layer 1 do OCR-MCP já aplicada na fonte.
    """
```

Mapeamento de erros:
- OCR `ToolError[E_OCR_*]` → `_PreOcrError` com o mesmo `code`.
- `asyncio.TimeoutError` → `_PreOcrError(code=E_MCP_UNAVAILABLE, message="OCR MCP não respondeu em {t}s", hint="docker compose ps | grep ocr-mcp")`.
- `httpx.ConnectError` / `anyio.ClosedResourceError` / outras falhas de transporte → após esgotar `connect_retries`, mesmo `E_MCP_UNAVAILABLE`.

### `_build_preocr_prompt(exams: list[str], fixed_plan_suffix: str) -> genai_types.Content`

- Pre: `exams` é `list[str]`; `fixed_plan_suffix` é a instrução textual curta enviada junto (ex.: "Siga o plano fixo a partir do passo 2").
- Post: retorna `Content(role="user", parts=[Part(text="EXAMES DETECTADOS (OCR pré-executado pelo CLI): <json-array>\n\n<suffix>")])`. Nenhum `inline_data`.
- Invariant: formato canônico estável (os testes asserting por regex pegam drift).

### `_run_agent(exams: list[str], correlation_id: str) -> Any`

- Pre: `exams` já veio de `_run_preocr` (pode estar vazia — mas `main()` nunca chega aqui se estiver vazia, ver AC2).
- Post: retorna Event final ou levanta via `asyncio.TimeoutError`.
- Invariant: `agent.tools` **não** contém a tool `extract_exams_from_image`; `Content` enviado não contém `inline_data`.

## Design by Contract

| Alvo | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `_run_preocr` | `image_bytes` não vazio; `mcp_url` sse válido; `timeout_s>0` | retorna `list[str]` OU levanta `_PreOcrError` | timeout absoluto respeitado; logs estruturados emitidos | AC1, AC6, AC7 | T010 `[DbC]`, T013 `[DbC]` |
| `_build_preocr_prompt` | `exams: list[str]` | `Content` com UMA Part textual, formato canônico, sem inline_data | nenhum Part binário presente | AC3 | T011 `[DbC]` |
| `_run_agent` (novo) | `exams: list[str]` não vazia | retorna Event ou levanta | tool OCR fora de `agent.tools` | AC4 | T012 `[DbC]` |
| `main` (aborto AC2) | `exams==[]` | `sys.exit(4)` com envelope `E_OCR_UNKNOWN_IMAGE` | runner **não** é invocado | AC2 | T014 |
| `main` (aborto AC6) | `_PreOcrError[E_MCP_UNAVAILABLE]` | `sys.exit(5)` com envelope | runner **não** é invocado | AC6 | T015 |

**Onde declarar no código**:
- Docstrings Google-style com `Pre`/`Post`/`Invariant` em `preocr.py`.
- `assert` em `_run_preocr` para `image_bytes` não-vazio (Pre).
- Pydantic `field_validator` no campo `exposed` (default + bool).

**Onde enforcar**:
- Testes `[DbC]` em `tests/generated_agent/test_preocr.py`, `test_agent_topology.py`, `test_main_preocr_wiring.py`.
- Snapshot do transpiler cobre a invariant de topologia (tool OCR não exposta).
- `code-reviewer` checa trace triplo AC ↔ DbC ↔ test.

## Dependências

Nenhuma nova. `mcp[cli]>=1.0,<2` já foi adicionado em Bloco 0006 e inclui `mcp.client.sse`.

## Riscos

- **R1 — CLI assume responsabilidade orquestradora adicional**. Se o OCR-MCP cair, nenhum run acontece. Mitigação: `depends_on: {ocr-mcp: {condition: service_healthy}}` já está no compose (Onda 4); AC6 cobre o caminho de falha.
- **R2 — Snapshot do transpiler quebra**. Esperado. `uv run pytest transpiler/tests/test_snapshots.py --snapshot-update` no commit dedicado (T026).
- **R3 — `_build_agent` regenerado diverge do arquivo handwritten**. Mitigação: T024 altera o template Jinja2 **antes** de T025 regenerar; T026 atualiza snapshots; diff esperado é **apenas** no McpToolset do OCR e na instruction. Diff maior → abort + investigar.
- **R4 — Retry `PREOCR_MCP_CONNECT_RETRIES=1` mascara problema persistente**. Mitigação: log `agent.preocr.connect.retry` cada tentativa; env permite `0` para desligar.
- **R5 — Fixture canônica continua retornando `[]` mesmo com chamada correta**. Significa que o dict `FIXTURES` não tem o hash real. Ação: registrar via `register_fixture(path, _SAMPLE_EXAMS)` no startup do OCR server (reuso de T040 da 0009, que ficou implementado). Commit curto, sem criar novo bloco.
- **R6 — ADR-0006 fica "parcialmente superseded" por duas ADRs (0009 e 0010)**. Mitigação: índice em `docs/adr/README.md` deixa ambas explícitas.

## Estratégia de validação

- **Unitário**:
  - `tests/generated_agent/test_preocr.py::test_calls_mcp_and_returns_exams` — mock `sse_client` + `ClientSession.call_tool`; asserta request body e retorno `list[str]` (T010).
  - `tests/generated_agent/test_preocr.py::test_build_prompt_contains_exam_list_and_no_inline_data` — chama `_build_preocr_prompt(["A","B"])` e asserta Part text + ausência de `inline_data` (T011).
  - `tests/generated_agent/test_preocr.py::test_timeout_raises_preocr_error` — mock que dorme > timeout; espera `_PreOcrError[E_MCP_UNAVAILABLE]` (T013).
  - `tests/generated_agent/test_agent_topology.py::test_ocr_tool_not_in_agent_tools` — constrói `_build_agent("cid")` e asserta que `extract_exams_from_image` não aparece em `toolset.tool_filter` do OCR (T012).
  - `tests/generated_agent/test_main_preocr_wiring.py::test_main_aborts_on_empty_exam_list` (T014) e `::test_main_aborts_on_mcp_unavailable` (T015) — monkey-patch `_run_preocr` para cada caminho.
- **Snapshot**:
  - `transpiler/tests/test_snapshots.py` — atualizado via `--snapshot-update` (T016/T026).
- **E2E**:
  - `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` com `.env` default → exit 0, tabela ASCII, `appointment_id` presente (T091).
  - Transcript salvo em `docs/EVIDENCE/0010-pre-ocr-invocation.md`.
- **Inspeção manual**:
  - Confirmar que `agent.run.start` NÃO loga `image_sha256_prefix` (porque a CLI não mais passa bytes ao runner); ou o campo é renomeado para `exam_count`.
  - `code-reviewer` aprova trace AC ↔ DbC ↔ Task ↔ Test.
