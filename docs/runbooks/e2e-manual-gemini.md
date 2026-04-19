# Runbook — E2E Manual com Gemini Real (T021 / AC1b)

**Versao:** 1.0 — 2026-04-19
**Audiencia:** Avaliador humano do desafio tecnico Senior IA.
**Objetivo:** Guia auto-suficiente para executar o fluxo completo de ponta a ponta com
`GOOGLE_API_KEY` valida — do clone do repositorio ate a verificacao do agendamento criado.

---

## 1. Objetivo e escopo

Este runbook cobre **AC1b**: execucao manual do fluxo E2E com Gemini real
(`gemini-2.5-flash`), confirmando que o agente gerado pelo transpilador JSON→ADK:

1. Le uma imagem de pedido medico via OCR MCP (SSE).
2. Consulta o catalogo de exames via RAG MCP (SSE, fuzzy match ≥ 80 %).
3. Cria um agendamento via `POST /api/v1/appointments` sem PII no payload.
4. Imprime tabela ASCII com os exames identificados, `appointment ID` e `correlation_id`.

**Fora do escopo deste runbook:**

- **AC1a** — suite E2E automatizada sem Gemini real, que ja roda em CI via
  `tests/e2e/test_ci_flow.py` (10 testes passando). Para reproduzir a suite CI, consulte
  `docs/EVIDENCE/0008-e2e-evidence-transparency.md`, secao "Comandos reproduziveis".

---

## 2. Pre-requisitos

| Requisito | Versao minima | Como verificar |
|---|---|---|
| Docker Desktop (daemon rodando) | v2.20 (compose v2) | `docker --version` e icone verde na bandeja do sistema |
| `git` | qualquer recente | `git --version` |
| `uv` | 0.11+ | `uv --version` |
| Python | 3.12 | `uv python install 3.12` (instala se ausente) |
| GOOGLE_API_KEY valida | — | ver abaixo |
| Espaco em disco livre | ~2 GB | para as 4 imagens Docker |

**Obtendo uma API Key do Google AI Studio:**

Acesse https://aistudio.google.com/app/apikey, clique em "Create API key" e copie a chave
(formato `AIza...`, ~39 caracteres).

Quota do free tier em abril/2026 para `gemini-2.5-flash`:

- 15 requisicoes por minuto (RPM).
- 1 milhao de tokens por dia.

O fluxo completo do agente (1 imagem, 3 exames) gasta aproximadamente 2.000–5.000 tokens.
A quota diaria raramente e um problema para execucao unica.

**Sistema operacional:** Windows 11, macOS ou Linux. Este runbook foi testado em
Windows 11 Pro 26100 + Docker Desktop 29.3.1 (ver `docs/EVIDENCE/0008-e2e-evidence-transparency.md`).

---

## 3. Preparacao

### 3.1 Clone do repositorio

```bash
git clone <repo-url>
cd Senior_IA
```

Output esperado (ultimas linhas):

```
Resolving deltas: 100% (NNN/NNN), done.
```

O diretorio `Senior_IA/` deve existir ao final.

### 3.2 Configurar variaveis de ambiente

```bash
cp .env.example .env
```

Abra `.env` em qualquer editor de texto e preencha a linha:

```
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Confirme que a linha a seguir nao foi alterada (deve estar exatamente assim):

```
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

Essa variavel instrui o SDK a usar a API direta do Google AI Studio, nao o Vertex AI.
Deixar como `TRUE` (ou remover a linha) causara erro `NOT_FOUND` ao invocar o modelo.

As demais variaveis (`OCR_MCP_URL`, `RAG_MCP_URL`, `SCHEDULING_OPENAPI_URL`) sao
sobrescritas automaticamente pelo `docker-compose.yml` via DNS interno do Compose —
nao e necessario ajusta-las.

### 3.3 Construir as imagens Docker

```bash
docker compose build
```

Serao construidas 4 imagens. Na primeira execucao o processo leva 5–10 minutos (download
de camadas base + instalacao de dependencias Python via `uv`). Execucoes subsequentes
usam o cache do Docker e levam ~30 segundos.

Output esperado ao final (verificar com `docker image ls | grep senior_ia`):

```
REPOSITORY                    TAG       IMAGE ID       CREATED         SIZE
senior_ia-generated-agent     latest    <hash>         X seconds ago   ...
senior_ia-scheduling-api      latest    <hash>         X seconds ago   ...
senior_ia-rag-mcp             latest    <hash>         X seconds ago   ...
senior_ia-ocr-mcp             latest    <hash>         X seconds ago   ...
```

Se alguma imagem estiver ausente, releia os logs do `docker compose build` em busca de
erros de dependencia ou conectividade.

### 3.4 Subir os servicos de infraestrutura

O agente e executado com `docker compose run` (um processo de vida curta); os tres
servicos de suporte ficam em background:

```bash
docker compose up -d ocr-mcp rag-mcp scheduling-api
```

Output esperado:

```
[+] Running 3/3
 - Container senior_ia-ocr-mcp-1          Started
 - Container senior_ia-rag-mcp-1          Started
 - Container senior_ia-scheduling-api-1   Started
```

### 3.5 Aguardar healthchecks

```bash
docker compose ps
```

Aguarde ate a coluna `STATUS` mostrar `healthy` para `scheduling-api` (pode levar ate
60 s — o container sobe o Uvicorn + carrega rotas). Os servidores MCP ficam em `running`
(nao expoe endpoint `/health`; o Compose usa `service_started` para eles).

Output esperado quando tudo esta pronto:

```
NAME                            IMAGE                         COMMAND                  SERVICE            CREATED          STATUS                    PORTS
senior_ia-ocr-mcp-1             senior_ia-ocr-mcp             "python -m ocr_mcp"      ocr-mcp            About a minute ago   Up About a minute (running)
senior_ia-rag-mcp-1             senior_ia-rag-mcp             "python -m rag_mcp"      rag-mcp            About a minute ago   Up About a minute (running)
senior_ia-scheduling-api-1      senior_ia-scheduling-api      "uvicorn scheduling_…"   scheduling-api     About a minute ago   Up About a minute (healthy)   0.0.0.0:8000->8000/tcp
```

Se `scheduling-api` ficar `unhealthy` apos 60 s, consulte a secao 5 (Troubleshooting),
cenario 3.

---

## 4. Execucao

### 4.1 Executar o agente

Este e o comando canonico que o avaliador deve rodar:

```bash
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

O container `generated-agent`:

1. Le a imagem de fixture montada em `/fixtures/` (volume read-only).
2. Chama `extract_exams_from_image` no `ocr-mcp` via MCP SSE.
3. Para cada exame retornado, chama `search_exam_code` no `rag-mcp`.
4. Chama `POST /api/v1/appointments` no `scheduling-api`.
5. Imprime a tabela ASCII final e encerra (exit code 0 em sucesso).

O agente usa `GOOGLE_API_KEY` do arquivo `.env` (carregado via `env_file` no
`docker-compose.yml`). As URLs dos servicos (`OCR_MCP_URL`, `RAG_MCP_URL`,
`SCHEDULING_OPENAPI_URL`) sao sobrescritas pelo Compose para resolver via DNS interno
(`ocr-mcp:8001`, `rag-mcp:8002`, `scheduling-api:8000`).

Tempo esperado de execucao: 15–60 s dependendo da latencia da API Gemini.

### 4.2 Saida esperada no terminal

O agente imprime logs estruturados em JSON seguidos de uma tabela ASCII ao final.
A forma esperada e:

```
{"ts": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "extract_exams_from_image", "correlation_id": "f47ac10b-..."}
{"ts": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "correlation_id": "f47ac10b-..."}
{"ts": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "correlation_id": "f47ac10b-..."}
{"ts": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "correlation_id": "f47ac10b-..."}
{"ts": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "schedule_appointment", "correlation_id": "f47ac10b-..."}

+-----+--------------------+---------+-------+
| #   | Exame              | Codigo  | Score |
+-----+--------------------+---------+-------+
| 1   | Hemograma Completo | HMG-001 | 0.98  |
| 2   | Glicemia de Jejum  | GLJ-002 | 0.96  |
| 3   | Colesterol Total   | COL-003 | 0.94  |
+-----+--------------------+---------+-------+
Appointment ID: apt-<id>  |  Scheduled: 2026-05-01T09:00:00
```

**Atencao:** os nomes de exames, codigos e scores variam conforme o matching do RAG
sobre a fixture. Os valores acima sao apenas a forma esperada — a saida real com Gemini
pode listar exames em ordem diferente ou com scores ligeiramente distintos.

Todos os registros de log devem compartilhar o **mesmo `correlation_id`** — este e o
sinal de que a propagacao de contexto via `X-Correlation-ID` funcionou de ponta a ponta
(OCR MCP, RAG MCP e scheduling-api recebem o mesmo ID).

O campo `patient_ref` no POST enviado a `scheduling-api` deve ter formato
`anon-<hash>` — nunca um nome ou CPF — confirmando que o PII Guard (dupla camada,
ADR-0003) atuou antes da requisicao sair do processo do agente.

### 4.3 Verificacao cruzada via API REST

Apos o agente encerrar, confirme que o agendamento foi persistido:

```bash
curl -s http://localhost:8000/api/v1/appointments | jq
```

Resposta esperada (array com pelo menos o registro recem-criado):

```json
[
  {
    "id": "apt-<id>",
    "status": "scheduled",
    "created_at": "2026-...",
    "patient_ref": "anon-<hash>",
    "exams": [
      {"name": "Hemograma Completo", "code": "HMG-001"},
      ...
    ],
    "scheduled_for": "2026-05-01T09:00:00Z"
  }
]
```

Para buscar o agendamento pelo ID retornado:

```bash
curl -s http://localhost:8000/api/v1/appointments/apt-<id> | jq
```

Se `jq` nao estiver instalado, substitua por `python -m json.tool` ou omita e leia o
JSON cru.

### 4.4 Swagger UI

Abra no navegador: http://localhost:8000/docs

Voce vera a documentacao interativa OpenAPI com os tres endpoints principais:

- `POST /api/v1/appointments` — criar agendamento.
- `GET  /api/v1/appointments/{id}` — buscar por ID.
- `GET  /api/v1/appointments` — listar agendamentos.

Recomenda-se tirar um screenshot desta pagina e salvar em
`docs/EVIDENCE/screenshots/swagger-<data>.png` como parte da evidencia (consulte a
secao 8 deste runbook).

---

## 5. Troubleshooting

### Cenario 1 — `E_AGENT_LLM_NO_API_KEY` no log do agente

**Sintoma:** O container do agente imprime um erro contendo `E_AGENT_LLM_NO_API_KEY` ou
`GOOGLE_API_KEY not set` e encerra com exit code diferente de 0.

**Causa:** O arquivo `.env` nao foi criado, ou a chave esta vazia/incorreta, ou o
`docker compose run` nao carregou o arquivo.

**Correcao:**
```bash
# Verificar se a chave chegou ao container
docker compose run --rm generated-agent env | grep GOOGLE_API_KEY
```
O output deve mostrar `GOOGLE_API_KEY=AIza...`. Se estiver vazio ou ausente, confirme
que `.env` existe na raiz do repositorio e que `GOOGLE_API_KEY` esta preenchida sem
espacos ou aspas ao redor do valor.

---

### Cenario 2 — `Cannot connect to the Docker daemon`

**Sintoma:** Qualquer comando `docker compose` falha com
`Cannot connect to the Docker daemon at unix:///var/run/docker.sock`.

**Causa:** O Docker Desktop nao esta em execucao no Windows.

**Correcao:** Abra o Docker Desktop pelo menu Iniciar. Aguarde ate o icone na bandeja
do sistema ficar verde (pode levar 30–60 s). Execute `docker info` para confirmar.

---

### Cenario 3 — `scheduling-api` fica `unhealthy` apos 60 s

**Sintoma:** `docker compose ps` mostra `unhealthy` na coluna STATUS para
`scheduling-api`.

**Causa comum:** porta 8000 ja em uso; erro de inicializacao (dependencia faltando);
path de healthcheck mal configurado.

**Correcao:**
```bash
docker compose logs scheduling-api
```
Leia as ultimas linhas. Se aparecer `address already in use`, veja o cenario 4. Se
aparecer `ModuleNotFoundError`, a imagem precisa ser reconstruida: `docker compose build
scheduling-api`.

---

### Cenario 4 — `port 8000 already in use`

**Sintoma:** `docker compose up` falha com
`Bind for 0.0.0.0:8000 failed: port is already allocated`.

**Causa:** Outro processo (Uvicorn local, outra instancia do Compose, servidor de
desenvolvimento) esta escutando na porta 8000.

**Correcao:**
```bash
# Derrubar stack anterior se ainda ativa
docker compose down

# No Windows: identificar o processo
netstat -ano | findstr :8000
# Anotar o PID e encerrar:
taskkill /PID <pid> /F
```

Ou altere a porta no `docker-compose.yml` (apenas para teste local):
`"8001:8000"` — nesse caso ajuste os comandos `curl` para usar `:8001`.

---

### Cenario 5 — `RESOURCE_EXHAUSTED` ou HTTP 429 da Gemini

**Sintoma:** O log do agente mostra `RESOURCE_EXHAUSTED` ou `quota exceeded`.

**Causa:** A quota de RPM (15/min) ou tokens diarios do free tier foi atingida.

**Correcao:** Aguarde 1 minuto e execute novamente. Se a quota diaria foi esgotada,
aguarde 24 h ou use uma API key diferente. Para reduzir o consumo de tokens, prefira
imagens de fixture menores (o `sample_medical_order.png` oficial e de tamanho adequado).

---

### Cenario 6 — `model_not_found` ou `NOT_FOUND` da Gemini

**Sintoma:** O log mostra `NOT_FOUND: models/gemini-2.5-flash is not found` ou similar.

**Causas possiveis:**

1. `GOOGLE_GENAI_USE_VERTEXAI` e `TRUE` — o SDK tenta resolver o modelo via Vertex AI,
   que requer projeto GCP e credenciais distintas.
2. O modelo `gemini-2.5-flash` nao esta disponivel na regiao ou conta usada.

**Correcao:** Verifique `.env` e confirme `GOOGLE_GENAI_USE_VERTEXAI=FALSE`. Se o
problema persistir com a key correta, teste no AI Studio se o modelo aparece disponivel
em https://aistudio.google.com/app/prompts/new_chat.

---

### Cenario 7 — `McpError: connection refused ocr-mcp:8001` ou `rag-mcp:8002`

**Sintoma:** O log do agente mostra `McpError` ou `ConnectionRefusedError` ao tentar
conectar nos servidores MCP.

**Causa:** Os servidores MCP ainda estao inicializando ou foram reiniciados pela politica
`on-failure:3`.

**Correcao:**
```bash
docker compose logs ocr-mcp
docker compose logs rag-mcp
```
Se os logs mostrarem `server.starting`, aguarde 30 s adicionais e execute o agente
novamente. Se mostrarem `exit 1` repetido, reconstrua: `docker compose build ocr-mcp`.

---

### Cenario 8 — `E_OCR_IMAGE_TOO_LARGE`

**Sintoma:** O agente retorna `E_OCR_IMAGE_TOO_LARGE` ou "Imagem > 5 MB nao suportada".

**Causa:** A imagem enviada decodificada ultrapassa 5 MB (limite do ADR-0008,
`E_OCR_IMAGE_TOO_LARGE`).

**Correcao:** Use exclusivamente a fixture oficial:
`docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png`

Essa imagem e montada via volume read-only (`./docs/fixtures:/fixtures:ro`) e foi
dimensionada para ficar dentro do limite.

---

### Cenario 9 — `E_PII_TIMEOUT`

**Sintoma:** O log mostra `E_PII_TIMEOUT` ou "pii_mask excedeu 5 s".

**Causa:** O motor Presidio/spaCy esta processando um texto muito longo (acima do normal).
Incomum com a fixture oficial; pode ocorrer se uma imagem personalizada gerar texto
extenso no OCR.

**Correcao:** Utilize a fixture oficial. Se o problema persistir, verifique a saude do
container: `docker compose logs ocr-mcp`. Reinicie se necessario:
`docker compose restart ocr-mcp`.

---

### Cenario 10 — `credsStore` error no Windows

**Sintoma:** `docker compose build` ou `docker pull` falha com
`error getting credentials: exit status 1` ou `exec: "docker-credential-desktop": ...`.

**Causa:** O Docker Desktop no Windows configura `credsStore: desktop.exe` em
`~/.docker/config.json`. Em alguns ambientes (WSL2, Git Bash) o helper nao e encontrado.

**Correcao:**
```bash
# Editar C:\Users\<seu-usuario>\.docker\config.json
# Remover ou comentar a chave "credsStore":
{
  "auths": {},
  "credStore": ""
}
```
Referencia: https://github.com/docker/for-win/issues (busca por `credsStore`).
Alternativa: executar todos os comandos no PowerShell como administrador ou dentro do
terminal integrado do Docker Desktop.

---

### Cenario 11 — `Permission denied` ao montar `/fixtures/`

**Sintoma:** `docker compose run` falha com `Permission denied` ou `invalid mount config`
ao tentar montar o volume de fixtures.

**Causa:** O path do repositorio contem espacos (ex.: `C:\Users\Meu Nome\Desktop\...`).
O Docker Desktop no Windows pode rejeitar paths com espacos ao processar volumes.

**Correcao:** Clone o repositorio em um caminho sem espacos:

```bash
git clone <repo-url> C:\dev\Senior_IA
cd C:\dev\Senior_IA
```

Alternativa: use o WSL2 — clone dentro do filesystem Linux do WSL (`~/Senior_IA`) e
execute todos os comandos Docker de la.

---

### Cenario 12 — Agente travado por mais de 60 s sem output

**Sintoma:** O container do agente e iniciado mas nenhum log aparece apos 60 s.

**Causa:** O Gemini pode estar demorando para responder (latencia alta) ou uma tool esta
aguardando resposta de um servidor MCP parado.

**Correcao:** Em outro terminal:
```bash
docker compose logs --tail=50 -f scheduling-api
docker compose logs --tail=50 -f ocr-mcp
docker compose logs --tail=50 -f rag-mcp
```
Identifique qual servico nao esta respondendo. Se o `scheduling-api` nao aparecer nos
logs durante o fluxo, o MCP de scheduling pode nao ter conseguido conectar — reinicie
a stack: `docker compose down && docker compose up -d ocr-mcp rag-mcp scheduling-api`.

O timeout total do agente e de 300 s (`E_AGENT_TIMEOUT`). Se esse limite for atingido,
o container encerra sozinho com exit code diferente de 0.

---

## 6. Registro da sua execucao

Copie o bloco abaixo, preencha cada campo e cole nas secoes de evidencia indicadas na
secao 8.

```markdown
### Execucao do avaliador — YYYY-MM-DD

- **Ambiente:** <SO e versao> / Docker Desktop <versao> / uv <versao>
- **GOOGLE_API_KEY valida:** [ ] sim  [ ] nao
- **`docker compose build` OK:** [ ] sim  tempo: ___ min
- **Healthchecks verdes em:** ___ segundos
- **Comando executado:**
  ```
  docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
  ```
- **Saida do agente (CLI):**
  ```
  <cole aqui a saida completa, incluindo os logs JSON e a tabela ASCII>
  ```
- **Appointment criado (ID):** ___
- **correlation_id observado nos logs:** ___
- **Screenshot do Swagger `/docs`:** `docs/EVIDENCE/screenshots/swagger-<data>.png`
- **Tempo total de execucao:** ___ s
- **Observacoes / desvios:** ___
```

---

## 7. Teardown

Encerre a stack e libere recursos:

```bash
docker compose down -v
```

O `-v` remove volumes anonimos criados pelo Compose (banco em memoria da
`scheduling-api`). As imagens Docker sao preservadas — o proximo `docker compose up`
nao precisa reconstruir.

Para liberar o espaco em disco das imagens (opcional):

```bash
docker system prune -f
```

Atencao: `docker system prune` remove **todas** as imagens e containers nao ativos no
sistema, nao apenas os deste projeto. Use com cautela se houver outros projetos Docker
no ambiente.

---

## 8. Anexar evidencia ao repositorio

Apos preencher o bloco da secao 6, cole-o nos dois arquivos de evidencia existentes:

**Arquivo 1:**
`docs/EVIDENCE/0006-generated-agent.md`, secao `## AC1b — Runbook de E2E Manual`,
no placeholder `## Saida real do Gemini (placeholder — T021)`.

**Arquivo 2:**
`docs/EVIDENCE/0008-e2e-evidence-transparency.md`, secao `## AC1b`, logo apos a tabela
ASCII de saida esperada.

Screenshot do Swagger: salve em `docs/EVIDENCE/screenshots/swagger-<data>.png`
(crie o diretorio `screenshots/` se nao existir).

Commit sugerido:

```bash
git add docs/EVIDENCE/0006-generated-agent.md \
        docs/EVIDENCE/0008-e2e-evidence-transparency.md \
        docs/EVIDENCE/screenshots/
git commit -m "docs(evidence): record manual E2E run [T021/AC1b]"
```

---

*Fim do runbook. Em caso de duvida sobre o escopo ou os contratos entre servicos,
consulte `docs/ARCHITECTURE.md`. Para a suite E2E automatizada (AC1a), consulte
`docs/EVIDENCE/0008-e2e-evidence-transparency.md`.*
