# Google ADK — Referência Consolidada

Fonte primária: docs oficial (`adk.dev`), repositório `google/adk-python`, codelabs e blog post oficial.

## 1. O que é o ADK
Framework open-source para construir, depurar e implantar agentes de IA. Disponível em Python, TS, Go e Java. Filosofia central: "managed context" — contexto tratado como código-fonte, com montagem estruturada em vez de concatenação de strings.

## 2. Instalação
```bash
pip install google-adk
```
Opcionalmente:
```bash
pip install "google-adk[extensions]"
```

## 3. Primitivas de Agente

### 3.1 LlmAgent / Agent
Agente baseado em LLM com ferramentas. `Agent` é alias para `LlmAgent`.
```python
from google.adk.agents.llm_agent import Agent

agent = Agent(
    name="researcher",
    model="gemini-2.5-flash",
    description="Agent that helps research topics.",
    instruction="You help users research topics thoroughly.",
    tools=[...],
)
```
Campos principais:
- `name` (str): identificador único.
- `model` (str): ex. `gemini-2.5-flash` (stable recomendado), `gemini-flash-latest`. `gemini-2.0-flash` está deprecated pelo Google desde 2025/2026 — não usar.
- `description` (str): usada para roteamento em multi-agent.
- `instruction` (str): prompt de sistema.
- `tools` (list): funções, `McpToolset`, built-ins.
- `sub_agents` (list): delegação.
- `output_key` (str, opcional): salva saída no state.

### 3.2 Workflow Agents
- **SequentialAgent** — pipeline ordenado (step A → B → C).
- **ParallelAgent** — execução concorrente com fan-out/fan-in.
- **LoopAgent** — iteração até condição de parada.
- **Custom Agents** — subclasse de `BaseAgent`.

Exemplo:
```python
from google.adk.agents import SequentialAgent

pipeline = SequentialAgent(
    name="scheduling_pipeline",
    sub_agents=[ocr_agent, rag_agent, booking_agent],
)
```

## 4. Ferramentas (Tools)
Tipos suportados:
- **Function tools** — funções Python com docstring + type hints.
- **MCP tools** — via `McpToolset`.
- **OpenAPI tools** — geração a partir de specs OpenAPI.
- **Built-in** — `google_search`, `code_execution`, etc.
- **Agent-as-tool** — outro agente exposto como ferramenta.

### 4.1 Function Tool mínima
```python
def get_weather(city: str) -> dict:
    """Get current weather for a city.
    Args:
        city: nome da cidade.
    Returns:
        dict com status e temperatura.
    """
    ...
```

### 4.2 MCP Toolset com SSE (crítico para o desafio)
> **Atenção:** o desafio exige **SSE**, não Streamable HTTP nem stdio.

```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

ocr_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url="http://ocr-mcp:8001/sse",
        headers={
            "Accept": "application/json, text/event-stream",
        },
    ),
    tool_filter=["extract_exams_from_image"],
)
```

Atualizado em 2026-04-19 após inspeção do pacote `google-adk==1.31.0` instalado: `SseConnectionParams` existe e é pública em `mcp_session_manager.py:89`; ela despacha para `sse_client()` (protocolo SSE legado — `GET /sse` + `POST /messages`), que é exatamente o que FastMCP serve com `mcp.run(transport="sse")`. `StreamableHTTPConnectionParams` (também presente) despacha para `streamablehttp_client()` — protocolo distinto (POST único) e **incompatível** com nosso servidor; usar essa classe causa `HTTP 405 Method Not Allowed`. A auditoria de 2026-04-18 (em `DESIGN_AUDIT.md § C2`) concluiu erroneamente que `SseConnectionParams` não existia no ADK atual; essa conclusão foi corrigida no § C2 nota de correção 2026-04-19 e em `ADR-0001 § Correção da correção (2026-04-19)`.

### 4.3 Uso síncrono vs assíncrono
- Em scripts CLI isolados, o padrão async com `exit_stack` / `await toolset.close()` é necessário.
- Para deploy em containers/serverless, **defina o agente e o `McpToolset` sincronamente** no módulo `agent.py`.

## 5. Runtime

### 5.1 Runner + SessionService
```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

session_service = InMemorySessionService()
session = await session_service.create_session(
    app_name="scheduling_app", user_id="u1", state={},
)

runner = Runner(
    app_name="scheduling_app",
    agent=root_agent,
    session_service=session_service,
)

content = types.Content(role="user", parts=[types.Part(text="agende estes exames")])
async for event in runner.run_async(
    session_id=session.id, user_id="u1", new_message=content
):
    print(event)
```

`InMemorySessionService` é adequado para desenvolvimento; produção usa `VertexAiSessionService` ou implementações persistentes.

### 5.2 Modos de execução
- `adk run .` — CLI interativo a partir do diretório do agente.
- `adk web` — Web UI local (porta 8000 por default).
- `adk api_server` — expõe agente como API HTTP.
- Uso programático — via `Runner` (como acima).

## 6. Estrutura mínima de projeto
```
my_agent/
├── __init__.py        # expõe `root_agent`
├── agent.py           # define `root_agent`
├── requirements.txt
└── .env               # GOOGLE_API_KEY, GOOGLE_GENAI_USE_VERTEXAI, etc.
```
`__init__.py`:
```python
from . import agent  # necessário para adk web / adk run
```

## 7. Variáveis de ambiente essenciais
| Variável | Uso |
|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` para usar API Key, `TRUE` para Vertex AI. |
| `GOOGLE_API_KEY` | Chave do AI Studio. |
| `GOOGLE_CLOUD_PROJECT` | (Vertex) project id. |
| `GOOGLE_CLOUD_LOCATION` | (Vertex) região. |

## 8. Multi-agent patterns
- **Coordinator/Dispatcher** — root agent com `sub_agents` + `description`-based routing.
- **Sequential Pipeline** — determinístico, bom para fluxos lineares (OCR → RAG → Booking).
- **Parallel Fan-out** — quando subtarefas são independentes.
- **Loop** — refino iterativo.

No desafio, o fluxo é claramente sequencial (Entrada → OCR → RAG → Agendamento → Saída), mas **um root agent LlmAgent com sub-agents/tools** também é viável e costuma ser mais flexível.

## 9. Boas práticas
- Docstrings ricas nas tools — o LLM as usa para decidir.
- `instruction` curto, imperativo e orientado a tarefa.
- Evitar estado global; usar `session.state`.
- Testar com `adk web` antes de empacotar.
- Fechar `McpToolset` em teardown quando usado fora de `adk web`.

## 10. Fontes
- `https://adk.dev/`
- `https://github.com/google/adk-python`
- `https://adk.dev/tools-custom/mcp-tools/`
- `https://codelabs.developers.google.com/your-first-agent-with-adk`
- `https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/`
