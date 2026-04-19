# Tutorial: transpilador JSON para Python (ADK)

## 1. Objetivo

Ao final deste tutorial você saberá escrever um arquivo `spec.json`, executar o
transpilador para gerar um pacote Python compatível com o Google ADK, e conferir
que o código gerado é sintaticamente válido. Nenhum serviço Docker é necessário
para esta etapa.

---

## 2. Pré-requisitos

- `uv 0.11+` instalado (verificar com `uv --version`).
- Python 3.12 disponível para o `uv` — instale se necessário:

  ```bash
  uv python install 3.12
  ```

- Repositório clonado. Todos os comandos assumem que o diretório raiz do repo é
  o ponto de partida.

Instale as dependências do transpilador:

```bash
cd transpiler
uv sync
```

O `uv sync` cria um virtualenv isolado em `transpiler/.venv` e instala Pydantic
v2 e Jinja2. Nenhum pacote de serviço (ADK, Presidio, FastAPI) é instalado aqui.

---

## 3. Como invocar

O entrypoint é o módulo `transpiler` invocado diretamente pelo interpretador:

```bash
# a partir de transpiler/
uv run python -m transpiler <spec.json> [-o <dir>] [-v]
```

Argumentos:

| Argumento | Obrigatorio | Padrao | Descricao |
|-----------|-------------|--------|-----------|
| `spec.json` | sim | — | Caminho para o arquivo de spec (UTF-8, max 1 MB). |
| `-o`, `--output` | nao | `.` (diretorio atual) | Diretorio pai onde `generated_agent/` sera criado. Deve estar dentro do cwd. |
| `-v`, `--verbose` | nao | desligado | Lista os arquivos gerados apos a transpilacao. |

Codigos de saida:

| Codigo | Significado |
|--------|-------------|
| `0` | Sucesso. |
| `1` | `E_TRANSPILER_SCHEMA` — spec.json invalido. |
| `2` | `E_TRANSPILER_RENDER` ou `E_TRANSPILER_RENDER_SIZE` — falha de renderizacao. |
| `3` | `E_TRANSPILER_SYNTAX` — `ast.parse` rejeitou o codigo gerado. |
| `4` | Erro inesperado (bug — abra issue). |

Erros sao impressos no `stderr` no formato canonico (uma linha por campo):
`code`, `message`, `hint`, `path`, `context`.

---

## 4. Contratos resumidos

### Schema AgentSpec

O schema completo esta documentado em dois lugares; nao e reproduzido aqui:

- Definicao formal em Python: [`docs/ARCHITECTURE.md § Schema Pydantic do JSON spec`](../ARCHITECTURE.md#schema-pydantic-do-json-spec)
- Criterios de aceitacao e guardrails: [`docs/specs/0001-agentspec-schema/spec.md`](../specs/0001-agentspec-schema/spec.md)

Pontos criticos para quem escreve o `spec.json`:

- `name` — regex `^[a-z0-9][a-z0-9-]*$`; unico no spec.
- `model` — valor fixo `"gemini-2.5-flash"` (outro valor provoca `E_TRANSPILER_SCHEMA`).
- `instruction` — maximo 4 096 bytes UTF-8.
- `mcp_servers` / `http_tools` — pelo menos um deve ser nao-vazio; caps de 10 e 20 itens respectivamente.
- `mcp_servers[*].name` deve ser unico dentro do spec.

### Gate `ast.parse`

Apos renderizar cada arquivo `.py`, o gerador executa `ast.parse(content)`.
Se a sintaxe for invalida o transpilador falha com `E_TRANSPILER_SYNTAX` (exit 3)
antes de escrever qualquer arquivo no disco. Decisao registrada em
[ADR-0002](../adr/0002-transpiler-jinja-ast.md).

---

## 5. Exemplos completos

### 5.1 Conteudo de `docs/fixtures/spec.example.json`

O arquivo completo esta em [`docs/fixtures/spec.example.json`](../fixtures/spec.example.json).
Campos essenciais:

```json
{
  "name": "medical-order-agent",
  "model": "gemini-2.5-flash",
  "mcp_servers": [
    {"name": "ocr", "url": "http://ocr-mcp:8001/sse",
     "tool_filter": ["extract_exams_from_image"]},
    {"name": "rag", "url": "http://rag-mcp:8002/sse",
     "tool_filter": ["search_exam_code", "list_exams"]}
  ],
  "http_tools": [
    {"name": "scheduling", "base_url": "http://scheduling-api:8000",
     "openapi_url": "http://scheduling-api:8000/openapi.json"}
  ],
  "guardrails": {"pii": {"enabled": true, "allow_list": []}}
}
```

### 5.2 Comando

Execute a partir do diretorio `transpiler/`:

```bash
uv run python -m transpiler ../docs/fixtures/spec.example.json -o /tmp/out -v
```

No Windows Git Bash, substitua `/tmp/out` por um caminho dentro do repo, por
exemplo `-o ./out`. O transpilador rejeita caminhos fora do diretorio de
trabalho atual (protecao contra path traversal, AC11).

### 5.3 Arvore de arquivos emitida

Saida esperada no `stdout` com `-v`:

```
Gerado em: /tmp/out/generated_agent
  .env.example
  Dockerfile
  __init__.py
  __main__.py
  agent.py
  logging_.py
  requirements.txt
```

O subdirectorio `generated_agent/` e sempre criado dentro do diretorio
informado em `--output`. A ordem de listagem e alfabetica.

### 5.4 Executar o agente gerado

```bash
cd /tmp/out/generated_agent
cp .env.example .env
# edite .env: defina GOOGLE_API_KEY, OCR_MCP_URL, RAG_MCP_URL, SCHEDULING_OPENAPI_URL
uv sync
uv run python -m generated_agent --image /caminho/para/pedido.jpg
```

O agente requer que os servicos MCP e a API de agendamento estejam no ar.
Para subir a stack completa, consulte `docker-compose.yml` na raiz do repo.

---

## 6. Troubleshooting

### 6.1 Spec JSON malformado — `E_TRANSPILER_SCHEMA`

**Sintoma**: exit code `1`; `stderr` mostra `code: E_TRANSPILER_SCHEMA`.

**Exemplo**:
```bash
uv run python -m transpiler spec_invalido.json -o ./out
# stderr:
# code: E_TRANSPILER_SCHEMA
# message: Campo `model` invalido: 'gpt-4' nao e um valor aceito. Valores permitidos: ['gemini-2.5-flash'].
# hint: Defina `model` como 'gemini-2.5-flash'. Outros modelos exigem nova ADR (ADR-0006).
```

**Correcao**: revise o `spec.json` contra o schema em
[`docs/ARCHITECTURE.md § Schema Pydantic`](../ARCHITECTURE.md#schema-pydantic-do-json-spec).
O transpilador reporta apenas o primeiro erro de validacao; corrija um campo por
vez ate o exit ser `0`.

### 6.2 Arquivo de spec inexistente

**Sintoma**: exit code `4`; `stderr` mostra `Erro inesperado: [Errno 2] No such file or directory`.
O CLI captura o `FileNotFoundError` no safety net e emite `E_TRANSPILER_RENDER`.

**Correcao**: verifique o caminho. O transpilador nao adiciona extensao automaticamente.

### 6.3 `ast.parse` falha no codigo emitido — `E_TRANSPILER_SYNTAX`

**Sintoma**: exit code `3`.

```
code: E_TRANSPILER_SYNTAX
message: Template produziu Python invalido em 'agent.py': invalid syntax (linha 42).
hint: Abra issue — transpilador produziu codigo invalido.
```

**Causa**: este erro **nao deve ocorrer com specs validos**. O gate `ast.parse`
garante que nenhum arquivo `.py` com erro de sintaxe e gravado em disco. Se
aparecer, e um bug do transpilador; abra issue com o `spec.json` que reproduz.

### 6.4 Diretorio de saida ja existe

**Sintoma**: exit code `2`; `stderr`:
```
code: E_TRANSPILER_RENDER
message: Diretorio de saida 'generated_agent' ja existe e contem 'agent.py'.
         Delete o diretorio ou escolha outro caminho (--output).
hint: Delete o diretorio de saida antes de re-gerar: rm -rf 'generated_agent'.
      Ou use -o para especificar um caminho diferente.
```

**Comportamento atual**: o transpilador **aborta** se `<output>/generated_agent/agent.py`
ja existir. Ele nao sobrescreve silenciosamente para evitar surpresas.

**Correcao**:
```bash
rm -rf /tmp/out/generated_agent
uv run python -m transpiler spec.json -o /tmp/out
# ou escolha outro diretorio de saida:
uv run python -m transpiler spec.json -o /tmp/out2
```

### 6.5 Campo `model` invalido

**Sintoma**: exit code `1`; `code: E_TRANSPILER_SCHEMA`; mensagem cita os
valores permitidos.

**Causa**: `model` e `Literal["gemini-2.5-flash"]`; qualquer outro valor e
rejeitado. Trocar de modelo exige nova ADR supersedendo
[ADR-0006](../adr/0006-spec-schema-and-agent-topology.md).

---

## 7. Onde estender

Para adicionar um template novo: crie o `.j2` em
[`transpiler/transpiler/templates/`](../../transpiler/transpiler/templates/),
registre-o nas listas `_TEMPLATE_FILES` / `_OUTPUT_FILES` de `generator.py`
(mesma posicao em ambas as listas) e escreva um snapshot test.
Arquivos `.py` gerados passam pelo gate `ast.parse` automaticamente.

Referencias:

- [`docs/specs/0002-transpiler-mvp/plan.md`](../specs/0002-transpiler-mvp/plan.md) — contratos DbC e riscos.
- [`docs/adr/0002-transpiler-jinja-ast.md`](../adr/0002-transpiler-jinja-ast.md) — justificativa Jinja2 + `ast.parse`.
- [`docs/adr/0006-spec-schema-and-agent-topology.md`](../adr/0006-spec-schema-and-agent-topology.md) — schema congelado.
