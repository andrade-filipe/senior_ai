# Tutorial 05 — Agente ADK Gerado (`generated-agent`)

## 1. Objetivo

Ao final deste tutorial você será capaz de:

- Executar o agente ADK de ponta a ponta dentro do stack Docker Compose.
- Entender o fluxo interno (OCR → RAG → Agendamento) e como cada etapa falha.
- Interpretar a saída — tabela ASCII de exames + `appointment_id`.
- Diagnosticar erros usando os códigos `E_AGENT_*`, `E_MCP_*` e variáveis de ambiente.

---

## 2. Pré-requisitos

| Item | Detalhe |
|---|---|
| Docker + Docker Compose v2.20+ | `docker compose version >= 2.20`. |
| Stack construída | `docker compose build` (todos os serviços). |
| `.env` com `GOOGLE_API_KEY` | Obrigatório. Sem ele o agente aborta com `E_AGENT_LLM_NO_API_KEY`. Copie `.env.example` para `.env` e preencha. |
| Serviços de infra em execução | `docker compose up -d ocr-mcp rag-mcp scheduling-api` antes de rodar o agente. |
| Imagem de pedido médico | Disponível em `docs/fixtures/sample_medical_order.png`. Montada em `/fixtures` no container. |

### Variáveis de ambiente relevantes

| Variável | Padrão (compose) | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | — (obrigatório em `.env`) | Chave de API do Google Generative AI. |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | Usa API direta (não Vertex AI). Fixado em `docker-compose.yml`. |
| `OCR_MCP_URL` | `http://ocr-mcp:8001/sse` | Endpoint SSE do servidor OCR MCP. |
| `RAG_MCP_URL` | `http://rag-mcp:8002/sse` | Endpoint SSE do servidor RAG MCP. |
| `SCHEDULING_OPENAPI_URL` | `http://scheduling-api:8000/openapi.json` | URL do spec OpenAPI da API de agendamento. |
| `LOG_LEVEL` | `INFO` | Nível de log (DEBUG, INFO, WARNING, ERROR). |

Os valores acima são injetados automaticamente pelo `docker-compose.yml` e sobrescrevem qualquer valor conflitante no `.env`.

---

## 3. Como invocar

### 3.1 Subir a infraestrutura

```bash
docker compose up -d ocr-mcp rag-mcp scheduling-api
```

Aguarde a API ficar saudável:

```bash
docker compose ps scheduling-api
# STATE deve ser "running (healthy)"
```

### 3.2 Executar o agente (modo CLI one-shot)

```bash
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

O container `generated-agent` é one-shot: executa, imprime o resultado em `stdout` e encerra. O `docker compose run` retorna o exit code do processo:

| Exit code | Significado |
|---|---|
| `0` | Sucesso — tabela ASCII impressa em stdout. |
| `1` | Arquivo de imagem não encontrado (`E_AGENT_INPUT_NOT_FOUND`). |
| `2` | Timeout de 300 s ultrapassado (`E_AGENT_TIMEOUT`). |
| `3` | Saída do LLM não válida contra o schema esperado (`E_AGENT_OUTPUT_INVALID`). |

### 3.3 Fornecer uma imagem personalizada

Monte o arquivo no container com `-v` e passe o caminho interno:

```bash
docker compose run --rm \
  -v /caminho/local/pedido.png:/input/pedido.png:ro \
  generated-agent --image /input/pedido.png
```

### 3.4 Rodar no ambiente local (fora do Docker) para desenvolvimento

```bash
cd generated_agent
uv run python -m generated_agent \
  --image ../docs/fixtures/sample_medical_order.png
```

As variáveis `OCR_MCP_URL`, `RAG_MCP_URL` e `SCHEDULING_OPENAPI_URL` devem apontar para os serviços MCP em execução (ajuste para `http://localhost:800X/sse` se os serviços estiverem expostos localmente ou use portas temporárias).

---

## 4. Contratos resumidos

- [`docs/ARCHITECTURE.md` § "generated_agent"](../ARCHITECTURE.md) — topologia `LlmAgent` único, tools, `before_model_callback`.
- [`docs/ARCHITECTURE.md` § "Diagrama de fluxo (pedido médico)"](../ARCHITECTURE.md#diagrama-de-fluxo-pedido-medico) — sequência OCR → RAG → API.
- [ADR-0001](../adr/0001-mcp-transport-sse.md) — transporte SSE; `SseConnectionParams` (ver § Correção da correção 2026-04-19).
- [ADR-0003](../adr/0003-pii-double-layer.md) — `before_model_callback` como camada 2 de PII.
- [ADR-0006](../adr/0006-spec-schema-and-agent-topology.md) — `LlmAgent` único; `model: gemini-2.5-flash`.
- [`docs/specs/0006-generated-agent/`](../specs/0006-generated-agent/) — spec, plan e tasks do bloco.
- [`docs/WALKTHROUGH.md`](../WALKTHROUGH.md) — narração passo a passo do fluxo E2E (a ser entregue).

---

## 5. Exemplos completos

### 5.1 Fluxo interno (sequencial)

O agente executa o plano fixo definido na `instruction` de `generated_agent/agent.py`:

```
1. extract_exams_from_image(image_base64)
        OCR MCP retorna lista de nomes (PII já mascarada).
2. search_exam_code(exam_name)   [uma chamada por exame, em paralelo]
        RAG MCP retorna ExamMatch{name, code, score} ou null.
3. Se score < 0.80 ou null → chama list_exams(limit=20) e apresenta candidatos.
4. POST /api/v1/appointments com todos os exames resolvidos.
5. Imprime tabela ASCII + appointment_id.
```

### 5.2 Saída esperada em stdout

```
+---+------------------------+-----------+
| # | Exame                  | Codigo    |
+---+------------------------+-----------+
| 1 | Hemograma Completo     | HMG-001   |
| 2 | Glicemia de Jejum      | GLI-001   |
| 3 | Colesterol Total       | COL-001   |
| 4 | TSH                    | TSH-001   |
| 5 | Creatinina             | CRE-001   |
+---+------------------------+-----------+
Appointment ID: apt-7f3a2b  |  Scheduled: 2026-05-01T09:00:00
```

Exame inconclusive (score abaixo de 0.80) aparece com `?` no código: `HMG-001?`.

### 5.3 Estrutura do JSON de saída interna (schema validado pelo runner)

O LLM deve retornar JSON estruturado antes que o runner formate a tabela:

```json
{
  "exams": [
    {"name": "Hemograma Completo", "code": "HMG-001", "score": 0.98, "inconclusive": false},
    {"name": "Glicemia de Jejum",  "code": "GLI-001", "score": 0.95, "inconclusive": false}
  ],
  "appointment_id": "apt-7f3a2b",
  "scheduled_for": "2026-05-01T09:00:00"
}
```

Se o LLM retornar JSON inválido ou sem os campos `exams`, `appointment_id` e `scheduled_for`, o runner imprime o erro em `stderr` e encerra com exit code 3.

### 5.4 Onde ver os logs de correlação

```bash
docker compose logs scheduling-api | grep correlation_id
```

Cada chamada `POST /api/v1/appointments` carrega o `X-Correlation-ID` gerado no startup do agente. Use-o para rastrear o ciclo completo:

```bash
CORR_ID="<uuid gerado pelo agente>"
docker compose logs ocr-mcp        | grep "$CORR_ID"
docker compose logs rag-mcp        | grep "$CORR_ID"
docker compose logs scheduling-api | grep "$CORR_ID"
```

### 5.5 Log de run bem-sucedido

```json
{"event": "agent.run.done", "level": "INFO",
 "correlation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
 "appointment_id": "apt-7f3a2b",
 "exam_count": 5}
```

---

## 6. Troubleshooting

### E_AGENT_LLM_NO_API_KEY

**Quando ocorre:** `GOOGLE_API_KEY` não está definida ou está vazia.

O agente não retorna código de domínio próprio — o SDK ADK lança `google.api_core.exceptions.PermissionDenied` ou similar. Verifique:

```bash
docker compose run --rm generated-agent env | grep GOOGLE_API_KEY
```

Solução: adicione `GOOGLE_API_KEY=AIza...` ao `.env` na raiz do repositório.

### E_AGENT_TIMEOUT (exit code 2)

**Quando ocorre:** a execução total do agente ultrapassa 300 s (5 min).

```json
{"error": {"code": "E_AGENT_TIMEOUT",
           "message": "Agente excedeu o tempo limite de 300 s.",
           "hint": "Verifique se os servicos MCP estao saudaveis (docker compose ps)."},
 "correlation_id": "..."}
```

Causas comuns: serviço MCP não respondendo (ver timeouts `E_OCR_TIMEOUT`, `E_RAG_TIMEOUT`), quota Gemini esgotada (ver abaixo), ou scheduling-api indisponível.

### MCP connection refused

**Quando ocorre:** o agente não consegue conectar ao endpoint SSE do OCR ou RAG MCP.

Sintoma nos logs:

```
httpx.ConnectError: [Errno 111] Connection refused
```

Verifique:

```bash
docker compose ps ocr-mcp rag-mcp
# Ambos devem estar "running"
```

Se não estiverem, suba com `docker compose up -d ocr-mcp rag-mcp` antes de rodar o agente. O `depends_on` do `docker-compose.yml` garante a ordem apenas quando os serviços são subidos juntos via `docker compose up`.

### Quota Gemini esgotada (RESOURCE_EXHAUSTED)

**Quando ocorre:** a chave de API atingiu o limite de requisições por minuto ou por dia da Gemini API.

Sintoma nos logs ADK:

```
google.api_core.exceptions.ResourceExhausted: 429 Resource has been exhausted
```

Solução: aguarde o reset da quota (geralmente 1 min para RPM) ou use uma chave diferente. Nenhum retry automático é implementado para esse código de status — o agente encerra.

### E_AGENT_OUTPUT_INVALID (exit code 3)

**Quando ocorre:** o LLM retornou texto que não é JSON válido, ou o JSON não contém `exams[]`, `appointment_id` e `scheduled_for`.

```json
{"error": {"code": "E_AGENT_OUTPUT_INVALID",
           "message": "Saida do agente nao corresponde ao schema esperado.",
           "hint": "Verifique se o agente retornou JSON valido com campos exams[], appointment_id, scheduled_for."},
 "correlation_id": "..."}
```

Solução: inspecione a `instruction` em `generated_agent/agent.py` — o plano fixo exige que o LLM emita JSON estruturado como último passo. Em ambiente de desenvolvimento, habilite `LOG_LEVEL=DEBUG` para ver o texto bruto retornado pelo LLM.

### scheduling-api retorna 422 (E_API_VALIDATION)

**Quando ocorre:** o campo `patient_ref` não segue o padrão `anon-[a-z0-9]+`, ou `exams[]` está vazio ou com itens duplicados, ou `scheduled_for` está no passado.

A `instruction` do agente proíbe retry para esse código. O agente reporta campo + motivo da mensagem Pydantic e encerra.

---

## 7. Onde estender

- **Spec e tasks:** [`docs/specs/0006-generated-agent/`](../specs/0006-generated-agent/)
- **Narrativa E2E:** [`docs/WALKTHROUGH.md`](../WALKTHROUGH.md) (a ser entregue pelo `software-architect`)
- **Ajustar instrução do agente:** campo `instruction` em `generated_agent/agent.py`. Qualquer mudança que altere o contrato com tools (nomes, ordem de chamada) exige revisão do `code-reviewer`.
- **Adicionar nova tool MCP:** adicione entrada em `mcp_servers` no `spec.json`, regere com `python -m transpiler spec.json -o ./generated_agent`, e rebuild. Novo campo no spec exige ADR supersedendo ADR-0006.
- **Trocar modelo LLM:** o campo `model` é `Literal["gemini-2.5-flash"]` (ADR-0006). Alterar exige ADR nova supersedendo ADR-0006 e ADR-0005.
- **Habilitar streaming:** atualmente desativado no MVP por segurança (ADR-0003 § "Risco operacional: stream completion"). Habilitar requer `after_model_callback` para PII na saída antes de ativar.
