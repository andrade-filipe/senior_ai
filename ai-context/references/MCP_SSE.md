# MCP + SSE — Referência Consolidada

## 1. O que é MCP
Model Context Protocol é um padrão aberto para expor "ferramentas" e "recursos" a agentes de IA, de forma agnóstica ao modelo. Um servidor MCP declara tools via JSON-RPC e o cliente (agente) as invoca.

## 2. Transporte SSE
- **Server-Sent Events** — canal HTTP unidirecional do servidor para o cliente, usando `text/event-stream`.
- No MCP, SSE é usado para o stream de respostas; o cliente envia requisições via POST para um endpoint (`/messages` ou similar) e recebe updates no stream SSE (`/sse`).
- **Observação:** o MCP oficial marcou SSE como *legacy/deprecated* em favor de "Streamable HTTP". O desafio, no entanto, exige SSE — devemos usar SSE explicitamente.

## 3. SDK Python oficial (FastMCP)
Instalação:
```bash
pip install "mcp[cli]"
```

### 3.1 Servidor FastMCP com SSE
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ocr-server")

@mcp.tool()
def extract_exams_from_image(image_base64: str) -> list[str]:
    """Extract list of exam names from a medical order image.
    Args:
        image_base64: imagem codificada em base64.
    Returns:
        lista de strings com os nomes detectados.
    """
    ...
    return ["Hemograma Completo", "Glicemia de Jejum"]

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8001)
```

### 3.2 Servidor RAG
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag-server")

@mcp.tool()
def search_exam_code(exam_name: str) -> dict:
    """Look up the exam code for a given exam name.
    Args:
        exam_name: nome do exame (ex.: 'Hemograma Completo').
    Returns:
        dict com campos `name`, `code`, `description`, `score`.
    """
    ...

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8002)
```

## 4. Cliente — integração com Google ADK
```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

SSE_HEADERS = {"Accept": "application/json, text/event-stream"}

ocr_tools = McpToolset(
    connection_params=SseConnectionParams(
        url="http://ocr-mcp:8001/sse",
        headers=SSE_HEADERS,
    ),
)
rag_tools = McpToolset(
    connection_params=SseConnectionParams(
        url="http://rag-mcp:8002/sse",
        headers=SSE_HEADERS,
    ),
)
```

Atualizado em 2026-04-19: `SseConnectionParams` é a classe correta para FastMCP com `transport="sse"` (protocolo SSE legado — `GET /sse` + `POST /messages`). A classe `StreamableHTTPConnectionParams` existe no ADK 1.31.0 mas fala outro protocolo (POST único em `/sse`) — usá-la contra nossos servidores causa `HTTP 405 Method Not Allowed`. Fonte primária: `google/adk/tools/mcp_tool/mcp_session_manager.py:89,120,400,408`. Corrige afirmação do 2026-04-18 (ver `DESIGN_AUDIT.md § C2 nota de correção 2026-04-19` e `ADR-0001 § Correção da correção (2026-04-19)`).
Use `tool_filter=[...]` para expor apenas tools específicas. Sempre chame `await toolset.close()` em scripts assíncronos.

## 5. Ciclo de vida e containers
- **SSE servers** são processos long-running; em Docker, rode com CMD blocking (`python -u server.py`).
- Exponha a porta SSE (`EXPOSE 8001`) e defina HEALTHCHECK com `curl -f http://localhost:8001/sse || exit 1` (ou endpoint `/health` custom).
- Em `docker-compose.yml`, use `depends_on` + `healthcheck` para garantir que o agente só inicie após os MCPs estarem prontos.

## 6. Protocolo SSE resumido
Requisição JSON-RPC do cliente → POST `/messages`:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```
Resposta no stream SSE:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}
```

## 7. Boas práticas
- **Tools pequenas e coesas** — uma tool, uma responsabilidade.
- **Docstrings detalhadas** — são parte do contrato com o LLM.
- **Validação de entrada** — tipos claros; rejeite inputs vazios.
- **Idempotência** quando possível.
- **Observabilidade** — log estruturado em cada chamada.
- **Timeouts** no cliente MCP para evitar travamentos.

## 8. Fontes
- `https://github.com/modelcontextprotocol/python-sdk`
- `https://modelcontextprotocol.github.io/python-sdk/`
- `https://adk.dev/tools-custom/mcp-tools/`
