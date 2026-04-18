# ADR-0001: Transporte MCP via SSE

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

O [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) define três transportes principais: `stdio` (processos locais), **Server-Sent Events (SSE)** (HTTP streaming unidirecional), e `Streamable HTTP` (transporte mais novo, bidirecional, que passou a ser recomendado em 2025).

O desafio técnico exige explicitamente em `docs/DESAFIO.md` (seção "Servidores MCP"): *"Os servidores devem usar transporte SSE"*. Não há espaço para interpretação — o transporte é imposto.

Esta decisão precede todas as outras relacionadas a MCP (estrutura de servidores, healthchecks, integração com o agente ADK).

## Alternativas consideradas

1. **stdio** — viável para experimentos locais, mas incompatível com a exigência do desafio de servidores em contêineres acessíveis via rede Docker. Os MCPs precisam ser consumidos por um agente em outro contêiner. Descartado.

2. **Streamable HTTP** — recomendação atual da equipe MCP, melhor para conexões bidirecionais, substitui SSE em novos projetos. Entretanto contradiz a exigência literal do desafio. Descartado.

3. **SSE (escolhido)** — cumpre o requisito, tem suporte maduro no SDK `mcp[cli]`, é ideal para o padrão "agente consome tools" (unidirecional do servidor para o cliente). Aceito.

## Decisão

Todos os servidores MCP (`ocr-mcp`, `rag-mcp`) usam transporte **SSE** via FastMCP:

```python
mcp.run(transport="sse", host="0.0.0.0", port=8001)
```

O agente ADK consome via `McpToolset(connection_params=StreamableHTTPConnectionParams(url="http://<service>:<port>/sse", headers={"Accept": "application/json, text/event-stream"}))`. A classe `StreamableHTTPConnectionParams` é a única disponível no ADK atual para MCP remoto e aceita endpoints SSE via compat.

O DESAFIO é literal quanto ao transporte **servidor**-side (SSE) e isso é mantido: `mcp.run(transport="sse", ...)` nos servidores. A escolha do classe-nome no cliente ADK é um detalhe de consumo, não alteração de decisão.

## Consequências

- **Positivas**: cumpre requisito; SDK maduro; contentorização trivial (um processo HTTP long-lived por servidor).
- **Negativas**: SSE é unidirecional — se futuramente precisarmos que o servidor consulte o agente ou mantenha contexto compartilhado, migraremos para Streamable HTTP (ADR nova). Healthcheck HTTP do SSE não é trivial: usamos `condition: service_started` no compose em vez de `service_healthy` para os MCPs.
- **Impacto**: `ai-context/references/MCP_SSE.md` consolida detalhes; `devops-engineer` sabe que MCPs usam `service_started`; o `generated_agent` depende de `OCR_MCP_URL` e `RAG_MCP_URL` apontando para endpoints `/sse`.

## Referências

- `docs/DESAFIO.md` — seção "Servidores MCP"
- `ai-context/references/MCP_SSE.md`
- https://modelcontextprotocol.io/docs/concepts/transports
- https://github.com/modelcontextprotocol/python-sdk
- https://adk.dev/tools-custom/mcp-tools/

> Corrigido em 2026-04-18 durante auditoria pré-implementação: (1) o MCP spec oficial marcou SSE como deprecated em favor de Streamable HTTP desde a versão 2024-11-05; mantemos SSE no servidor porque é exigência literal do DESAFIO.md, porém fica registrado como risco de incompatibilidade futura. (2) No cliente ADK, a classe correta é `McpToolset` (não `MCPToolset`) e o único `connection_params` disponível é `StreamableHTTPConnectionParams` (a classe `SseConnectionParams` citada no corpo da decisão não existe mais no ADK atual). StreamableHTTPConnectionParams consome endpoints SSE via compat — o servidor continua 100% SSE.
