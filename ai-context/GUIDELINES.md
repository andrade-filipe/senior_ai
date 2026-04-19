# Diretrizes de Engenharia

Padrões obrigatórios para todo código, teste, infraestrutura e documentação. Cabe ao `code-reviewer` fazer cumprir.

## 1. Código Python

- **Versão**: Python 3.12 (compose base `python:3.12-slim`).
- **Gerenciador de dependências**: `uv` (exclusivo). Um `pyproject.toml` por serviço; sem pyproject na raiz. Fixado em [ADR-0005](../docs/adr/0005-dev-stack.md).
- **Dependências principais**: Pydantic v2, FastAPI, Uvicorn, `google-adk`, `mcp[cli]`, `presidio-analyzer`, `presidio-anonymizer`, spaCy (`pt_core_news_lg`), Jinja2, `rapidfuzz`.
- **Comandos canônicos**:
  ```bash
  uv sync                         # instalar deps e criar .venv
  uv run pytest --cov             # testes com cobertura
  uv run ruff check .             # lint
  uv run ruff format .            # format
  uv run mypy .                   # type-check (strict em transpiler/ e security/)
  ```
- **Lint**: `ruff check`. Regras mínimas: `E`, `F`, `I`, `UP`, `B`, `S` (bandit via ruff), `C901` (McCabe), `SIM` (simplify), `RET` (return), `N` (naming).
- **Type checking**: `mypy --strict` em `transpiler/` e `security/`. Demais módulos: `mypy` sem `--strict`, mas com type hints onde faz sentido.
- **Estrutura**: imports absolutos; um arquivo expõe no máximo uma classe pública principal.
- **Docstrings**: obrigatórias em toda função pública e em toda tool MCP (Google style: Args/Returns/Raises).
- **Comentários**: escrever apenas o *porquê* quando não é óbvio. Sem "código comentado", sem TODOs órfãos.
- **Heurística de função**: ≤ 25 linhas **contando apenas o corpo** (exclui docstring + type hints); ≤ 3 parâmetros; flag-args (bool que alterna comportamento) proibidos — split em duas funções ou use kwargs explícitos.

## 1.1 Clean Code (Python procedural)

Aplicamos um subconjunto pragmático adaptado a código procedural/funcional (não-OOP). Checklist completo (obrigatório vs recomendado, com dispensas explícitas de SOLID e Object Calisthenics) vive em [`.claude/agents/code-reviewer.md`](../.claude/agents/code-reviewer.md) § "Critérios Clean Code (Python procedural)" — `code-reviewer` é quem faz cumprir no checkpoint #2.

Resumo do que é **obrigatório** (violação = BLOCKED):
- Type hints em toda função pública (args + return).
- Nomes revelam intenção; `snake_case` PEP 8; sem `data`/`temp`/`x` fora de lambdas/loops.
- Exceções customizadas herdam de `ChallengeError`; `except:` cego proibido; mensagens ricas (o quê / por quê / como corrigir).
- Sem dead code; sem TODO órfão (exige link para ADR/issue/Txxx).

Resumo do que é **recomendado** (violação = CHANGES REQUESTED):
- Funções ≤ 25 linhas (heurística, não dogma).
- ≤ 3 parâmetros; flag-args proibidos.
- Comments só explicam **porquê**; docstring cobre **o quê**.
- McCabe complexity < 12 (via `C901`).
- DRY: duplicação ≥ 3× → extrair helper.

Explicitamente **dispensados**: SOLID (código é procedural), Object Calisthenics (dogmas OOP), cyclomatic complexity como gate (usamos como sinal, não como veto), dogma "funções de 4–20 linhas" (Uncle Bob).

## 2. Validação e erros

- Inputs externos sempre passam por Pydantic v2.
- Mensagens de erro explicitam: **o que** está errado, **por que**, **como corrigir** (com exemplo).
- Exceções customizadas herdam de uma base do módulo (ex.: `TranspilerError`, `PIIError`).
- Nenhum `except:` cego; sempre captura específico.
- **Política cross-service** fixada em [ADR-0008](../docs/adr/0008-robust-validation-policy.md) e operacionalizada em [`docs/ARCHITECTURE.md § Robustez e guardrails`](../docs/ARCHITECTURE.md). Taxonomia completa `E_*`, caps de tamanho, timeouts, shape canônico (`{code, message, hint, path, context}`), correlation_id e no-PII-in-logs — **ler ADR-0008 antes de decidir** qualquer código de erro novo ou limite numérico. Reuso de código entre módulos proibido; novo `E_*` exige PR que atualize a tabela.

## 3. Segurança

- **PII**: mascarada antes de qualquer chamada a LLM, antes de persistir, antes de serializar para logs.
- **Segredos**: exclusivamente via `.env`. `.env` em `.gitignore`. `.env.example` commitado.
- **Logs**: estruturados (JSON ou key=value). Nunca incluem valores brutos detectados como PII. Entradas de auditoria guardam hash, tipo, operação.
- **MCP**: servidores expostos apenas na rede interna do compose. API FastAPI exposta no host em `:8000`.
- **Input validation** na borda: API, cada tool MCP, CLI do transpilador. Caps concretos (tamanho de `image_base64`, `text`, `exams[]`, `spec.json`, etc.) na **tabela de guardrails** em [`docs/ARCHITECTURE.md § Robustez e guardrails`](../docs/ARCHITECTURE.md) / [ADR-0008](../docs/adr/0008-robust-validation-policy.md). Violação de cap vira `E_*` conforme tabela; valor é rejeitado na borda, antes de invocar motor pesado (Presidio, base64 decoder, `json.loads`).
- **Dependências**: pinadas (`requirements.txt` com `==` ou `~=`).

## 4. Testes

- **Framework**: `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `pytest-cov`, `pytest-regressions`.
- **TDD pragmático** (fixado em [ADR-0004](../docs/adr/0004-sdd-tdd-workflow.md)):
  - **Test-first obrigatório** em `transpiler/` e `security/` — código onde regressão silenciosa é cara. `qa-engineer` escreve o teste RED; engenheiro de domínio só começa a implementar após o teste falhar.
  - **Same-commit** (testes junto do código, ordem livre) em `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, Dockerfiles, compose — escrever teste falhando antes desses traz pouco sinal extra.
- **Cobertura mínima**: 80 % em `transpiler/` e `security/`. CI falha abaixo disso. Relatório anexado às evidências.
- **Determinismo**: nenhuma chamada real a LLM, OCR externo, ou rede em unit/integration.
- **Transpilador**: cada fixture JSON tem snapshot de saída + `ast.parse` do código gerado.
- **API**: testes via `httpx.AsyncClient`, não `TestClient` sync.
- **MCP**: servidor rodado em subprocesso para teste de integração; mock para unit.
- **E2E**: um teste orquestrado que sobe `docker compose`, roda a CLI do agente gerado com uma imagem fixture e valida o estado da API.

## 5. Git e CI

- **Branches**: `main` protegida mentalmente. Features em `feat/<slug>`, fixes em `fix/<slug>`, docs em `docs/<slug>`, infra em `chore/<slug>`.
- **Commits**: Conventional Commits em inglês.
  - `feat(transpiler): add jinja template for sequential agent`
  - `fix(security): strip whitespace before regex match`
  - `test(mcp): add ocr-mcp integration smoke test`
  - `chore(docker): bump python base image`
- **Tamanho**: commits pequenos e focados. Um commit = uma ideia revisável.
- **História**: a sequência de commits deve contar a evolução do software de forma legível como narrativa. Ordem típica: contratos/specs/ADRs → código que implementa → testes que validam → evidências. Agrupe por tema ou camada; não misture intenções distintas no mesmo commit.
- **Mensagens**: corpo opcional explicando *por que*, não *o que*. Commits de implementação citam ID da task (`T020`) ou AC do spec.
- **`.env` e artefatos gerados** nunca entram no git (ver `.gitignore`).
- **CI gate** ([ADR-0005](../docs/adr/0005-dev-stack.md)): `.github/workflows/ci.yml` roda `ruff check`, `ruff format --check`, `mypy`, `pytest --cov --cov-fail-under=80`, `docker build` em cada push/PR. **PR não merge se CI falhar** — nenhuma exceção; se CI está errado, corrige o CI.

## 6. Documentação

- **Separação humano-vs-IA** (obrigatória, detalhada em `ai-context/WORKFLOW.md` → "Layout da documentação"):
  - `docs/` é entrega para avaliadores humanos. Estável, narrativo, português.
  - `ai-context/` é contexto operacional dos subagentes. Iterativo, denso.
  - `code-reviewer` reprova PR que misture os dois públicos no mesmo arquivo.
- **Idioma**: textos narrativos em português; código, identificadores, commits, issues em inglês.
- **README final** (raiz) cobre: stack, arquitetura, quickstart (3 comandos), evidências, seção "Transparência e Uso de IA".
- **`docs/REQUIREMENTS.md`** enumera R01..Rn; specs citam `linked_requirements: [Rxx]` no frontmatter.
- **`docs/specs/NNNN-<slug>/`** é o artefato primário do SDD (spec + plan + tasks). Templates em `docs/specs/README.md`.
- **`docs/ARCHITECTURE.md`** usa mermaid para diagramas; atualizado apenas quando contrato muda.
- **`docs/EVIDENCE/`** acumula logs/prints por marco (um arquivo por bloco).
- **`docs/adr/`** contém ADRs numeradas (`NNNN-*.md`), imutáveis após aceite; mudanças geram ADR nova que *supersede* a anterior. Template + índice em `docs/adr/README.md`.
- **`ai-context/references/`** guarda notas técnicas consolidadas; pode evoluir livremente, mas deve refletir o estado atual das libs.
- **`ai-context/LINKS.md`** é atualizado **no mesmo commit** em que uma fonte externa for consultada. Sem rastreabilidade → sem merge.
- **`ai-context/STATUS.md`** é atualizado a cada checkpoint humano.

## 7. Infra / Docker

- Um serviço = um `Dockerfile`.
- `CMD` no formato `exec` (lista).
- `HEALTHCHECK` em todos os serviços HTTP.
- `depends_on` com `condition: service_healthy` para a API; `service_started` para MCPs.
- `.dockerignore` sempre presente.
- Compose não expõe portas desnecessárias ao host.

## 8. Processo com IA

- **SDD antes de código**: nenhum teste ou código é escrito sem `spec.md` + `plan.md` + `tasks.md` aprovados no checkpoint #1. Regra formalizada em [ADR-0004](../docs/adr/0004-sdd-tdd-workflow.md).
- **Revisão obrigatória**: nenhum código entra sem passar por `code-reviewer` e por revisão humana do usuário (checkpoint #2).
- **Contratos públicos**: qualquer alteração exige ADR nova (`software-architect` abre, usuário aprova).
- **Prompts claros**: ao invocar um subagente, citar arquivos relevantes + ID do spec do bloco + ADRs aplicáveis.
- **Determinismo de saída**: o transpilador deve ser determinístico; código gerado estável entre execuções para a mesma entrada.
- **Rastreabilidade por commit**: mensagem de commit de implementação cita `Txxx` (task ID) ou `ACn` (critério de aceitação) do spec.

## 9. Rastreabilidade

- `ai-context/STATUS.md` é atualizado a cada checkpoint.
- Cada marco tem `docs/EVIDENCE/<marco>.md`.
- Cada contrato alterado tem ADR em `docs/adr/`.
- Cada bug encontrado em revisão tem um commit corretivo rastreável.

## 10. Design by Contract

Contratos semânticos declarados em docstring (seções `Pre`, `Post`, `Invariant`, `Raises`). Pydantic cobre pré-condição de dados; assert cobre fronteira de função crítica; teste cobre pós/invariante. Nenhuma lib extra. Cada entrada da tabela "Design by Contract" do `plan.md` tem teste correspondente em `tasks.md`.

**Convenção de tagging (triplo-trace)**: a tabela DbC do `plan.md` carrega colunas `AC ref` (aponta para o AC do `spec.md`) e `Task ref` (aponta para a task de teste em `tasks.md`). Testes que exercem contrato DbC formal são marcados `[DbC]` em `tasks.md`, ao lado de `[P]` se paralelizáveis. O `spec.md` fecha o triângulo com a sub-seção **Rastreabilidade DbC** ao final de "Critérios de aceitação", listando o mapa AC ↔ linha DbC. Esse triplo-trace (spec ↔ plan ↔ tasks) é condição de aprovação pelo `code-reviewer`: uma linha DbC sem AC referenciado, ou um `AC ref` sem sub-seção Rastreabilidade, ou um `Task ref` sem tag `[DbC]` na task correspondente → `CHANGES REQUESTED`.
