# Transpilador JSON → Código Python ADK — Referência de Design

## 1. Objetivo
Ler uma especificação JSON de agente e **gerar um pacote Python executável** que instancia agentes usando o Google ADK.

## 2. Abordagem recomendada
Três abordagens possíveis; vamos comparar rapidamente:

| Abordagem | Prós | Contras |
|---|---|---|
| **Templates Jinja2** | Simples, legível, fácil de manter. Saída lembra código escrito à mão. | Menos rigor em validação da AST resultante. |
| **Montagem via `ast` (stdlib)** | Garante que a saída é sintaxe Python válida por construção. | Verboso; difícil de manter para estruturas grandes. |
| **Híbrido (Jinja2 + `ast.parse` de verificação)** | Legibilidade + validação. | Um pouco mais de código. |

**Recomendação:** **Híbrido** — templates Jinja2 por sua legibilidade, com `ast.parse(generated_code)` ao final como *smoke check* e `ruff format`/`black` para formatação final.

## 3. Schema JSON (draft)
```json
{
  "$schema": "https://agents.lab/schema/v1.json",
  "name": "scheduling_assistant",
  "description": "Assistente de agendamento de exames",
  "model": "gemini-flash-latest",
  "instruction": "Você ajuda pacientes a agendar exames...",
  "tools": [
    {
      "type": "mcp_sse",
      "name": "ocr_tools",
      "url": "http://ocr-mcp:8001/sse",
      "tool_filter": ["extract_exams_from_image"]
    },
    {
      "type": "mcp_sse",
      "name": "rag_tools",
      "url": "http://rag-mcp:8002/sse",
      "tool_filter": ["search_exam_code"]
    },
    {
      "type": "openapi",
      "name": "scheduling_api",
      "spec_url": "http://scheduling-api:8000/openapi.json"
    }
  ],
  "sub_agents": [],
  "guardrails": {
    "before_model": ["pii_mask"],
    "after_tool": []
  },
  "output": {
    "target": "cli",
    "package_name": "scheduling_agent"
  }
}
```

## 4. Validação do input
- **Pydantic v2** para definir o schema e validar antes de gerar código.
- Rejeitar referências a ferramentas com `type` desconhecido.
- Exigir `name` único por tool.
- Validar URLs (scheme http/https, não vazias).
- `model` deve pertencer a allowlist configurável.

## 5. Etapas do transpilador
1. **Carregar** JSON.
2. **Validar** via Pydantic → `AgentSpec`.
3. **Resolver** (ex.: baixar spec OpenAPI se aplicável).
4. **Renderizar** templates Jinja2 → strings de código.
5. **Verificar** com `ast.parse` — falhar rápido se gerou sintaxe inválida.
6. **Formatar** com `black`/`ruff format` (opcional mas desejável).
7. **Escrever** arquivos: `<pkg>/__init__.py`, `<pkg>/agent.py`, `<pkg>/requirements.txt`, `<pkg>/Dockerfile`, `<pkg>/.env.example`.
8. **Relatório** — imprimir resumo (arquivos criados, tools detectadas, warnings).

## 6. Estrutura do transpilador
```
transpiler/
├── __init__.py
├── __main__.py            # python -m transpiler spec.json -o ./out
├── cli.py                 # argparse/typer
├── schema.py              # Pydantic: AgentSpec, ToolSpec, ...
├── loader.py              # carrega + valida JSON
├── generator.py           # orquestra render → verify → write
├── templates/
│   ├── agent.py.j2
│   ├── __init__.py.j2
│   ├── requirements.txt.j2
│   ├── Dockerfile.j2
│   └── env.example.j2
└── tests/
    ├── fixtures/
    └── test_generator.py
```

## 7. Template `agent.py.j2` (esboço)
```jinja
from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

_SSE_HEADERS = {"Accept": "application/json, text/event-stream"}

{% for tool in tools_mcp %}
{{ tool.name }} = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url="{{ tool.url }}", headers=_SSE_HEADERS),
    {% if tool.tool_filter %}tool_filter={{ tool.tool_filter|tojson }},{% endif %}
)
{% endfor %}

root_agent = Agent(
    name="{{ spec.name }}",
    model="{{ spec.model }}",
    description={{ spec.description|tojson }},
    instruction={{ spec.instruction|tojson }},
    tools=[
        {% for tool in tools_mcp %}{{ tool.name }},{% endfor %}
    ],
)
```

## 8. Mensagens de erro
Sempre explicitar:
- **O que** está errado (campo, valor).
- **Por que** (regra violada).
- **Como corrigir** (exemplo válido).

Exemplo: `tools[1].url must be a non-empty http(s) URL — received ''. Example: "http://ocr-mcp:8001/sse"`.

## 9. Testes do transpilador
- **Unit** — cada template isolado, schema Pydantic.
- **Integração** — JSON fixture → código gerado → `ast.parse` → `importlib.util` de smoke (sem executar LLM).
- **Snapshot** — `pytest-regressions` para pegar regressões no output.
- **Property-based** (opcional) — `hypothesis` para gerar specs válidas aleatoriamente.

## 10. Observações
- Nunca execute o código gerado dentro do transpilador; separação estrita.
- O transpilador não baixa modelos nem se conecta a APIs externas durante a geração (offline por default). `resolve_openapi=true` é opt-in.
- Versione o schema JSON (`$schema` + `version` no output).
