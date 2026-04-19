# Tutorial 02 — Servidor MCP de OCR (`ocr-mcp`)

## 1. Objetivo

Ao final deste tutorial você será capaz de:

- Subir o serviço `ocr-mcp` de forma isolada dentro da rede Docker Compose.
- Entender a única tool exposta (`extract_exams_from_image`) e suas garantias de PII.
- Chamar a tool via script Python dentro da rede Compose.
- Diagnosticar as falhas mais comuns usando os códigos `E_OCR_*`.

---

## 2. Pré-requisitos

| Item | Detalhe |
|---|---|
| Docker + Docker Compose v2.20+ | `docker compose version` deve retornar `>= 2.20`. |
| Imagem construída | `docker compose build ocr-mcp` ou `docker compose build` (full stack). |
| `.env` presente | Copie `.env.example` para `.env` na raiz. As variáveis obrigatórias para este serviço são `LOG_LEVEL` e `PII_DEFAULT_LANGUAGE`. Sem `GOOGLE_API_KEY` — o OCR MCP não chama LLM. |
| `security/` compilável | O módulo `ocr-mcp` importa `security.pii_mask` em tempo de execução. O Dockerfile do `ocr-mcp` inclui `security/` como dependência local. |

O serviço **não publica porta ao host**. Isso é intencional (ver `docker-compose.yml`, bloco `ocr-mcp`, sem `ports:`). Acessá-lo diretamente a partir do host requer `docker compose exec` ou um container auxiliar na mesma rede.

---

## 3. Como invocar

### 3.1 Subir apenas o serviço

```bash
docker compose up -d ocr-mcp
```

O servidor SSE fica disponível dentro da rede Compose em `http://ocr-mcp:8001/sse`. A linha nos logs indica pronto:

```
{"event": "startup", "service": "ocr-mcp", "level": "INFO"}
```

### 3.2 Verificar que o endpoint SSE responde

Como o serviço não tem porta ao host, use `docker compose exec`:

```bash
docker compose exec ocr-mcp \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/sse', timeout=2).status)"
```

Saída esperada: `200` (conexão SSE estabelecida).

### 3.3 Chamar a tool via script Python dentro da rede

O agente usa `McpToolset` + `StreamableHTTPConnectionParams` (ADR-0001). Para testes manuais dentro da rede, crie um script e execute-o em um container com acesso à rede Compose:

```python
# test_ocr_tool.py — rodar via:
# docker compose run --rm generated-agent python /scripts/test_ocr_tool.py
import asyncio
import base64
import pathlib

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams


async def main() -> None:
    image_bytes = pathlib.Path("/fixtures/sample_medical_order.png").read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode()

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="http://ocr-mcp:8001/sse",
            headers={"Accept": "application/json, text/event-stream"},
        ),
        tool_filter=["extract_exams_from_image"],
    )

    tools, _ = await toolset.__aenter__()
    ocr_tool = next(t for t in tools if t.name == "extract_exams_from_image")
    result = await ocr_tool.run_async(args={"image_base64": image_b64}, tool_context=None)
    print(result)
    await toolset.close()


asyncio.run(main())
```

A imagem de amostra está em `docs/fixtures/sample_medical_order.png`, montada em `/fixtures` no container `generated-agent` conforme `docker-compose.yml`.

---

## 4. Contratos resumidos

Os contratos públicos desta tool estão definidos em:

- [`docs/ARCHITECTURE.md` § "Assinaturas exatas das tools MCP"](../ARCHITECTURE.md#assinaturas-exatas-das-tools-mcp) — assinatura congelada.
- [`docs/ARCHITECTURE.md` § "Contratos entre subsistemas"](../ARCHITECTURE.md#contratos-entre-subsistemas) — formato de entrada e saída.
- [ADR-0001](../adr/0001-mcp-transport-sse.md) — justificativa do transporte SSE; classe `StreamableHTTPConnectionParams` no cliente.
- [ADR-0003](../adr/0003-pii-double-layer.md) — onde e como `pii_mask` é aplicado (camada 1 dentro do OCR MCP).
- [`docs/specs/0003-mcp-ocr-rag/`](../specs/0003-mcp-ocr-rag/) — spec, plan e tasks do bloco.

---

## 5. Exemplos completos

### 5.1 Resposta para a imagem de fixture

A imagem `docs/fixtures/sample_medical_order.png` tem um SHA-256 registrado no dicionário de fixtures do servidor. A chamada retorna sempre a mesma lista (OCR é determinístico no MVP):

```json
["Hemograma Completo", "Glicemia de Jejum", "Colesterol Total", "TSH", "Creatinina"]
```

O fixture PNG contém intencionalmente um CPF fictício (`111.444.777-35`) e nome de paciente para exercitar o pipeline de PII. Após `pii_mask`, esses valores aparecem como `<CPF>` e `<PERSON>` na saída.

Exemplo com PII presente na imagem:

```
Entrada (texto extraído): "Paciente: João da Silva, CPF: 111.444.777-35"
Saída da tool: ["Hemograma Completo", "Glicemia de Jejum", "Colesterol Total", "TSH", "Creatinina"]
```

Os nomes de exames não contêm PII — o mascaramento atua sobre qualquer token pessoal que apareça misturado no resultado bruto antes de retornar.

### 5.2 Imagem desconhecida (hash não registrado)

Para qualquer imagem fora do dicionário de fixtures, a tool retorna lista vazia sem erro:

```json
[]
```

### 5.3 Log de uma chamada bem-sucedida

```json
{
  "ts": "2026-04-19T10:00:00.123Z",
  "level": "INFO",
  "service": "ocr-mcp",
  "event": "tool.called",
  "extra": {
    "tool": "extract_exams_from_image",
    "duration_ms": 38.4,
    "exam_count": 5
  }
}
```

---

## 6. Troubleshooting

### E_OCR_IMAGE_TOO_LARGE

**Quando ocorre:** bytes decodificados do `image_base64` excedem 5 MB.

```json
{"code": "E_OCR_IMAGE_TOO_LARGE", "message": "Imagem > 5 MB não suportada",
 "hint": "Comprima ou reduza a imagem antes de enviar",
 "context": {"bytes_received": 6291456, "bytes_max": 5242880}}
```

Solução: use `convert -resize 1200x1200 entrada.png saida.png` (ImageMagick) ou equivalente antes de codificar em base64.

### E_OCR_INVALID_INPUT

**Quando ocorre:** string passada não é base64 válido (RFC 4648), está vazia ou contém caracteres ilegais.

```json
{"code": "E_OCR_INVALID_INPUT", "message": "`image_base64` não é base64 válido",
 "hint": "Codifique a imagem em base64 padrão (RFC 4648)"}
```

Solução: use `base64.b64encode(bytes).decode()` em Python ou `base64 -w 0 arquivo.png` no shell.

### E_OCR_TIMEOUT

**Quando ocorre:** o processamento interno (lookup + PII mask) excede 5 s. Improvável com o mock determinístico, mas possível se o motor Presidio estiver sobrecarregado.

```json
{"code": "E_OCR_TIMEOUT", "message": "OCR não respondeu em 5 s",
 "hint": "Verifique se `ocr-mcp` está saudável (`docker compose ps`)"}
```

Solução: `docker compose ps ocr-mcp` para verificar estado; `docker compose logs --tail=50 ocr-mcp` para inspecionar erros do motor PII; reinicie com `docker compose restart ocr-mcp`.

### Servidor não sobe (unhealthy / exit 1)

O healthcheck (`python -c "import urllib.request; urllib.request.urlopen(...)"`) falha se o `security/` não carregar. Verifique:

```bash
docker compose logs ocr-mcp | grep -i error
```

Causas comuns: `spaCy` sem o modelo `pt_core_news_lg` (baixar via `uv run python -m spacy download pt_core_news_lg` dentro do container), ou dependência ausente no ambiente.

### PNG válido mas lista retorna vazia

Comportamento esperado para imagens fora do dicionário de fixtures no MVP. O servidor não faz OCR real — apenas retorna listas pré-definidas para hashes conhecidos. Adicionar novos fixtures requer editar `ocr_mcp/ocr_mcp/fixtures.py` e reconstruir a imagem Docker.

---

## 7. Onde estender

- **Spec e tasks:** [`docs/specs/0003-mcp-ocr-rag/`](../specs/0003-mcp-ocr-rag/)
- **Adicionar novo fixture de imagem:** edite `ocr_mcp/ocr_mcp/fixtures.py` — inclua o hash SHA-256 da nova imagem e a lista de exames esperados em `FIXTURES`. Reconstrua com `docker compose build ocr-mcp`.
- **Substituir mock por OCR real:** implemente a função `_do_ocr` em `ocr_mcp/ocr_mcp/server.py` sem alterar a assinatura pública da tool — os guardrails (tamanho, timeout, PII) permanecem inalterados.
- **Ajustar timeout:** constante `_OCR_TIMEOUT_S` em `ocr_mcp/ocr_mcp/server.py`. Mudança acima de 10 s deve ser justificada em ADR nova (ADR-0008 § Timeouts).
