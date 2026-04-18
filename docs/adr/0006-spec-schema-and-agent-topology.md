# ADR-0006: Schema do JSON spec + topologia do agente gerado

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

O transpilador precisa de um **schema estável** do seu input (`spec.json`). E o agente gerado precisa de uma **topologia** definida: um único `LlmAgent`? uma composição `SequentialAgent`/`ParallelAgent`? Essas duas decisões estão acopladas — o schema precisa expressar a topologia, e a topologia precisa ser modelável pelo schema.

O desafio pede que o agente coordene OCR → RAG → agendamento. Isso pode ser modelado em vários formatos no ADK.

## Alternativas consideradas

### Schema do spec
1. **Minimalista (escolhido)** — cobrir só o necessário para o desafio: `LlmAgent` único com suas ferramentas. Schema pequeno e congelado.
2. **Extensível desde o MVP** — suportar `SequentialAgent`/`ParallelAgent`/`LoopAgent` já. Transpilador mais complexo; risco de inchar sem demanda real.
3. **Híbrido (minimalista agora + campos reservados)** — schema fechado mas com nota documentada sobre como estender. Nós aplicamos parte disso: versionamento via ADR nova.

### Topologia do agente
1. **LlmAgent único (escolhido)** — um `LlmAgent` que usa `McpToolset` (OCR+RAG) + tool HTTP para a API de agendamento + `before_model_callback` de PII. A instrução do agente orquestra o fluxo linguisticamente.
2. **SequentialAgent com 3 sub-agents** (OCR → RAG → Booking) — melhor separação mas mais tokens, mais latência, mais overhead de contexto.
3. **LlmAgent principal + sub-agent de booking** — meio termo; não se justifica dado o fluxo linear.

## Decisão

### Schema Pydantic v2 do `AgentSpec` (congelado)

```python
class McpServerSpec(BaseModel):
    name: str
    url: str                              # ex.: http://ocr-mcp:8001/sse
    tool_filter: list[str] | None = None  # None = todas as tools

class HttpToolSpec(BaseModel):
    name: str
    base_url: str                         # ex.: http://scheduling-api:8000
    openapi_url: str | None = None        # opcional: gerar tools a partir de OpenAPI

class PiiGuardSpec(BaseModel):
    enabled: bool = True
    allow_list: list[str] = []

class GuardrailSpec(BaseModel):
    pii: PiiGuardSpec = Field(default_factory=PiiGuardSpec)

class AgentSpec(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str
    model: Literal["gemini-2.5-flash"]    # Literal para auditoria
    instruction: str                       # prompt multiline, imperativo
    mcp_servers: list[McpServerSpec]
    http_tools: list[HttpToolSpec]
    guardrails: GuardrailSpec = Field(default_factory=GuardrailSpec)
```

Qualquer campo adicional exige **nova ADR** supersedendo esta. O schema é a fronteira pública do transpilador.

### Topologia

Agente gerado é um **único `LlmAgent`** com:
- `tools`: junção de `McpToolset(connection_params=StreamableHTTPConnectionParams(url=...))` por item em `mcp_servers` + tool HTTP (OpenAPI ou adapter manual) por item em `http_tools`.
- `model`: valor do campo `model` do spec.
- `instruction`: valor do campo `instruction` do spec.
- `before_model_callback`: injetado se `guardrails.pii.enabled=True`.

### Como estender no futuro

Quando surgir necessidade de composição:
- Abrir nova ADR que supersede esta.
- Adicionar campo `children: list[AgentSpec]` + `type: Literal["llm", "sequential", "parallel"]` ao schema.
- Introduzir novo template Jinja2 por tipo.

Até lá, o schema é fechado.

## Consequências

- **Positivas**: transpilador enxuto, testes de snapshot estáveis, `code-reviewer` tem critério objetivo (qualquer campo novo no JSON → schema rejeita). `Literal["gemini-2.5-flash"]` força revisão consciente quando trocarmos o modelo.
- **Negativas**: suporte a composição de agentes vira trabalho futuro. Aceito porque o desafio não exige.
- **Impacto**: `transpiler-engineer` implementa exatamente esse schema; `adk-mcp-engineer` sabe que o template do `agent.py.j2` assume LlmAgent; `qa-engineer` cria fixtures JSON nesse formato.

## Referências

- `docs/ARCHITECTURE.md` — seção "Schema Pydantic do JSON spec"
- `ai-context/references/ADK.md`
- `ai-context/references/TRANSPILER.md`
- https://adk.dev/agents/llm-agents/
- https://adk.dev/tools-custom/mcp-tools/
- https://docs.pydantic.dev/latest/

> Corrigido em 2026-04-18 durante auditoria pré-implementação: (1) `Literal["gemini-2.0-flash"]` foi atualizado para `Literal["gemini-2.5-flash"]` porque o modelo anterior foi descontinuado pelo Google (ver ADR-0005 nota de correção). (2) Construtor da toolset MCP atualizado de `MCPToolset(SseConnectionParams(url=...))` para `McpToolset(connection_params=StreamableHTTPConnectionParams(url=...))` — a classe `SseConnectionParams` não existe no ADK atual (ver ADR-0001 nota de correção). (3) Parâmetro `instruction` (singular) confirmado como correto contra `https://adk.dev/agents/llm-agents/`.
