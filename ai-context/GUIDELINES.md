# Diretrizes de Engenharia

Padrões obrigatórios para todo código, teste, infraestrutura e documentação. Cabe ao `code-reviewer` fazer cumprir.

## 1. Código Python

- **Versão**: Python 3.12 (compose base `python:3.12-slim`).
- **Dependências**: Pydantic v2, FastAPI, Uvicorn, `google-adk`, `mcp[cli]`, `presidio-analyzer`, `presidio-anonymizer`, spaCy (`pt_core_news_lg`), Jinja2.
- **Formatação**: `ruff format` (ou `black`). Nunca commitar código não formatado.
- **Lint**: `ruff check`. Regras mínimas: `E`, `F`, `I`, `UP`, `B`, `S` (bandit via ruff).
- **Type checking**: `mypy --strict` em `transpiler/` e `security/`. Demais módulos: `mypy` sem `--strict`, mas com type hints onde faz sentido.
- **Estrutura**: imports absolutos; um arquivo expõe no máximo uma classe pública principal.
- **Docstrings**: obrigatórias em toda função pública e em toda tool MCP (Google style: Args/Returns/Raises).
- **Comentários**: escrever apenas o *porquê* quando não é óbvio. Sem "código comentado", sem TODOs órfãos.

## 2. Validação e erros

- Inputs externos sempre passam por Pydantic v2.
- Mensagens de erro explicitam: **o que** está errado, **por que**, **como corrigir** (com exemplo).
- Exceções customizadas herdam de uma base do módulo (ex.: `TranspilerError`, `PIIError`).
- Nenhum `except:` cego; sempre captura específico.

## 3. Segurança

- **PII**: mascarada antes de qualquer chamada a LLM, antes de persistir, antes de serializar para logs.
- **Segredos**: exclusivamente via `.env`. `.env` em `.gitignore`. `.env.example` commitado.
- **Logs**: estruturados (JSON ou key=value). Nunca incluem valores brutos detectados como PII. Entradas de auditoria guardam hash, tipo, operação.
- **MCP**: servidores expostos apenas na rede interna do compose. API FastAPI exposta no host em `:8000`.
- **Input validation** na borda: API, cada tool MCP, CLI do transpilador.
- **Dependências**: pinadas (`requirements.txt` com `==` ou `~=`).

## 4. Testes

- **Framework**: `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `pytest-cov`, `pytest-regressions`.
- **Cobertura mínima**: 80% em `transpiler/` e `security/`. Relatório anexado às evidências.
- **Determinismo**: nenhuma chamada real a LLM, OCR externo, ou rede em unit/integration.
- **Transpilador**: cada fixture JSON tem snapshot de saída + `ast.parse` do código gerado.
- **API**: testes via `httpx.AsyncClient`, não `TestClient` sync.
- **MCP**: servidor rodado em subprocesso para teste de integração; mock para unit.
- **E2E**: um teste orquestrado que sobe `docker compose`, roda a CLI do agente gerado com uma imagem fixture e valida o estado da API.

## 5. Git

- **Branches**: `main` protegida mentalmente. Features em `feat/<slug>`, fixes em `fix/<slug>`, docs em `docs/<slug>`, infra em `chore/<slug>`.
- **Commits**: Conventional Commits em inglês.
  - `feat(transpiler): add jinja template for sequential agent`
  - `fix(security): strip whitespace before regex match`
  - `test(mcp): add ocr-mcp integration smoke test`
  - `chore(docker): bump python base image`
- **Tamanho**: commits pequenos e focados. Um commit = uma ideia revisável.
- **Mensagens**: corpo opcional explicando *por que*, não *o que*.
- **`.env` e artefatos gerados** nunca entram no git (ver `.gitignore`).

## 6. Documentação

- **Separação humano-vs-IA** (obrigatória, detalhada em `ai-context/WORKFLOW.md` → "Layout da documentação"):
  - `docs/` é entrega para avaliadores humanos. Estável, narrativo, português.
  - `ai-context/` é contexto operacional dos subagentes. Iterativo, denso.
  - `code-reviewer` reprova PR que misture os dois públicos no mesmo arquivo.
- **Idioma**: textos narrativos em português; código, identificadores, commits, issues em inglês.
- **README final** (raiz) cobre: stack, arquitetura, quickstart (3 comandos), evidências, seção "Transparência e Uso de IA".
- **`docs/ARCHITECTURE.md`** usa mermaid para diagramas; atualizado apenas quando contrato muda.
- **`docs/EVIDENCE/`** acumula logs/prints por marco (um arquivo por bloco).
- **`docs/adr/`** contém ADRs numeradas (`NNNN-*.md`), imutáveis após aceite; mudanças geram ADR nova que *supersede* a anterior. Template + índice em `docs/adr/README.md`.
- **`ai-context/references/`** guarda notas técnicas consolidadas; pode evoluir livremente, mas deve refletir o estado atual das libs.
- **`ai-context/STATUS.md`** é atualizado a cada checkpoint humano.

## 7. Infra / Docker

- Um serviço = um `Dockerfile`.
- `CMD` no formato `exec` (lista).
- `HEALTHCHECK` em todos os serviços HTTP.
- `depends_on` com `condition: service_healthy` para a API; `service_started` para MCPs.
- `.dockerignore` sempre presente.
- Compose não expõe portas desnecessárias ao host.

## 8. Processo com IA

- **Revisão obrigatória**: nenhum código entra sem passar por `code-reviewer` e por revisão humana do usuário.
- **Contratos públicos**: qualquer alteração exige ADR.
- **Prompts claros**: ao invocar um subagente, citar arquivos relevantes e o critério de aceitação do bloco.
- **Determinismo de saída**: o transpilador deve ser determinístico; código gerado estável entre execuções para a mesma entrada.

## 9. Rastreabilidade

- `ai-context/STATUS.md` é atualizado a cada checkpoint.
- Cada marco tem `docs/EVIDENCE/<marco>.md`.
- Cada contrato alterado tem ADR em `docs/adr/`.
- Cada bug encontrado em revisão tem um commit corretivo rastreável.
