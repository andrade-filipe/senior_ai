# ADR-0005: Stack de desenvolvimento (uv + Gemini + GitHub Actions)

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

Decisões de stack que atravessam todos os serviços e bloqueiam o início da implementação: gerenciador de dependências, provedor de LLM, estrutura de pacotes Python, pipeline de CI. Sem consenso nesses pontos, cada engenheiro de domínio tomaria decisões locais incoerentes.

## Alternativas consideradas

### Gerenciador de dependências
1. **uv (escolhido)** — ~10× mais rápido que pip, lock-file determinístico (`uv.lock`), amigável em Docker multi-stage, roda `python -m` sem ambiente ativado.
2. **poetry** — maduro, lock-file robusto, mas bem mais lento que uv; curva de aprendizado para quem não conhece.
3. **pip + requirements.txt** — tradicional, sem lock-file real; tende a "funciona aqui, quebra lá" em datas futuras.

### Estrutura do repo
1. **Um `pyproject.toml` por serviço (escolhido)** — `transpiler/`, `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, `security/` cada um com seu pyproject. Dockerfiles instalam só o necessário → imagens enxutas.
2. **Monorepo com pyproject único na raiz** — simples para dev local; mas gera imagens inchadas e rebuild cascata.

### Provedor de LLM
1. **Google Gemini via API key (escolhido)** — `gemini-2.0-flash` com variável `GOOGLE_API_KEY` e `GOOGLE_GENAI_USE_VERTEXAI=FALSE`. Zero credenciais GCP; tier gratuito generoso; reprodutível.
2. **Gemini via Vertex AI** — produção-grade mas exige projeto GCP + ADC + permissões. Overkill para um desafio.
3. **LiteLLM multi-provider** — adiciona camada de abstração e dependências; ADK é projetado para Gemini.
4. **Mock LLM** — contraria a exigência do desafio de usar LLM real.

### CI/CD
1. **GitHub Actions mínimo (escolhido)** — workflow único: ruff + mypy + pytest (cov ≥ 80 %) + docker build, rodando em push/PR. Badge verde vai ao README.
2. **Pre-commit + Actions completo com matriz** — mais robusto; overhead para prazo curto.
3. **Makefile/scripts locais apenas** — sem gate automatizado; nenhuma evidência pública.

## Decisão

### Dependências e ambientes
- **uv** como gerenciador exclusivo de dependências Python.
- Um `pyproject.toml` por serviço; nenhum pyproject na raiz.
- Comandos canônicos:
  ```bash
  uv sync                         # instalar deps e criar .venv
  uv run pytest --cov             # rodar testes com cobertura
  uv run ruff check .             # lint
  uv run ruff format .            # format
  uv run mypy .                   # type-check (strict em transpiler/ e security/)
  ```

### LLM
- Provedor: **Google Gemini direct API**.
- Modelo default: `gemini-2.0-flash` (campo `model` no spec JSON é `Literal` para auditar mudanças).
- Variáveis de ambiente: `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE`.

### CI
- GitHub Actions em `.github/workflows/ci.yml` (criado no primeiro bloco que compila):
  - `lint`: `uv run ruff check .` + `uv run ruff format --check .`
  - `type`: `uv run mypy .` (strict nos paths configurados)
  - `test`: `uv run pytest --cov --cov-fail-under=80` nos módulos com threshold
  - `docker`: build de cada serviço (sem push) para garantir que o Dockerfile compila
- Dispara em `push` e `pull_request`.

## Consequências

- **Positivas**: instalação rápida (uv); imagens Docker pequenas; reprodutibilidade (lock-file); CI é evidência pública de qualidade; avaliador reproduz com 2 comandos (`uv sync && uv run pytest`).
- **Negativas**: uv é mais recente que pip/poetry — alguns engenheiros precisam aprender sintaxe. Mitigação: documentar comandos em `ai-context/GUIDELINES.md`. Per-service pyproject obriga coordenação entre serviços quando uma lib é compartilhada; mitigado porque só `security/` é consumido por outros (via import), e seu pyproject expõe a lib.
- **Impacto**: `devops-engineer` gera Dockerfiles usando `uv pip install --system` no stage final; `qa-engineer` roda CI localmente via `uv run`; todo `requirements.txt` em docs é substituído por `uv sync` + `pyproject.toml` fragment.

## Referências

- https://docs.astral.sh/uv/
- https://docs.astral.sh/uv/guides/integration/docker/
- https://ai.google.dev/gemini-api/docs
- https://google.github.io/adk-docs/ — seção Gemini API
- https://docs.github.com/actions/using-workflows
