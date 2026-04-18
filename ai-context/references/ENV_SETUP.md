# ENV_SETUP — Bootstrap do ambiente Python local

Referência de setup para qualquer colaborador (humano ou agente) que precise reproduzir o ambiente de desenvolvimento deste repositório. Estado-alvo descrito em [ADR-0005](../../docs/adr/0005-dev-stack.md): **uv** como gerenciador exclusivo + **Python 3.12** + **`pyproject.toml` por serviço** (sem pyproject na raiz).

Este documento vive em `ai-context/` enquanto estamos em fase de implementação; a versão final para o avaliador será absorvida na seção "Como rodar" do `README.md` durante a Onda 5 (Bloco 0008).

## Pré-requisitos

- Windows 10/11 com **winget** (v1.x) disponível **ou** PowerShell 5.1+.
- Acesso de rede à `github.com`, `astral.sh` e `docs.astral.sh`.
- Git Bash ou qualquer shell POSIX-like para rodar os comandos `uv` (opcional — PowerShell funciona igualmente).

Nenhum Python do sistema é usado. O uv instala e gerencia uma cópia de Python 3.12 isolada em `~/AppData/Roaming/uv/python/`.

## Passo 1 — Instalar o `uv`

**Preferencial (winget)**:

```bash
winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
```

**Fallback (installer oficial via PowerShell)** — usar se winget estiver bloqueado ou indisponível:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
```

Ambos colocam `uv.exe` no `PATH` da próxima sessão de shell. Na sessão atual, o PATH só é atualizado depois de reabrir o terminal.

Verificação: `uv --version` deve retornar `uv 0.11.x` ou superior.

## Passo 2 — Instalar Python 3.12 via uv

```bash
uv python install 3.12
```

Saída típica: download de ~20 MB + instalação em 3–5 s. O binário fica em `~/AppData/Roaming/uv/python/cpython-3.12.*-windows-x86_64-none/python.exe`.

Verificação: `uv python list --only-installed` deve listar uma entrada `cpython-3.12.x-windows-x86_64-none`.

Não é necessário adicionar Python 3.12 ao `PATH` do sistema — `uv` resolve automaticamente quando cada `pyproject.toml` declara `requires-python = ">=3.12,<3.13"`.

## Passo 3 — Usar o ambiente em cada serviço

Cada serviço tem seu próprio `pyproject.toml` (ADR-0005, sem workspace raiz). Entrada padrão:

```bash
cd transpiler/             # ou ocr_mcp/, rag_mcp/, scheduling_api/, security/, generated_agent/
uv sync                    # cria .venv e instala deps do pyproject.toml + uv.lock
uv run pytest --cov        # roda testes no venv do serviço
uv run ruff check .        # lint
uv run mypy .              # type-check (strict em transpiler/ e security/)
```

O comando `uv run <cmd>` injeta o venv sem precisar ativar (`source .venv/bin/activate`). Isso funciona em Git Bash, PowerShell e cmd sem diferenças.

## Manutenção

- **Atualizar uv**: `winget upgrade astral-sh.uv` (ou `uv self update` se instalado via installer).
- **Atualizar Python 3.12**: `uv python install 3.12 --upgrade` (uv baixa a versão patch mais recente).
- **Remover Python gerenciado**: `uv python uninstall 3.12`.
- **Desinstalar uv**: `winget uninstall astral-sh.uv`.

## Fontes oficiais consultadas

- https://docs.astral.sh/uv/getting-started/installation/ — métodos de instalação do uv em Windows (winget listado como opção oficial).
- https://docs.astral.sh/uv/guides/install-python/ — `uv python install` como mecanismo first-class para gerenciar versões.
- https://github.com/astral-sh/python-build-standalone — binários Python standalone usados pelo uv.
- https://docs.astral.sh/uv/concepts/projects/ — `pyproject.toml` por projeto (alinhado com decisão ADR-0005).

## Não contemplados aqui

- Criação de `pyproject.toml` em cada serviço (isso é `T001` de cada bloco, dono é o engineer especialista).
- Configuração de GitHub Actions (`.github/workflows/ci.yml`) — criada no primeiro bloco que compila código (Onda 1).
- Dockerfiles — competência do `devops-engineer` na Onda 4.
