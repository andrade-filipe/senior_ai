---
id: 0002-transpiler-mvp
status: proposed
---

## Abordagem técnica

Transpilador implementado conforme [ADR-0002](../../adr/0002-transpiler-jinja-ast.md) (Jinja2 + `ast.parse`), [ADR-0006](../../adr/0006-spec-schema-and-agent-topology.md) (schema + topologia LlmAgent único) e [ADR-0008](../../adr/0008-robust-validation-policy.md) (taxonomia centralizada de erros, guardrails de path/size, shape canônico). Estrutura:

```
transpiler/
├── __init__.py         # reexporta AgentSpec (Bloco 1) + public API
├── __main__.py         # entrypoint `python -m transpiler`
├── cli.py              # parser argparse + códigos de saída
├── schema.py           # (Bloco 1 — já pronto)
├── generator.py        # render + ast gate + write
├── templates/          # Jinja2 templates (.j2)
│   ├── agent.py.j2
│   ├── __init__.py.j2
│   ├── requirements.txt.j2
│   ├── Dockerfile.j2
│   └── .env.example.j2
└── errors.py           # (Bloco 1)
```

Fluxo de `generator.render(spec: AgentSpec, output_dir: Path) -> None`:
1. Carregar templates via `jinja2.Environment(loader=FileSystemLoader, autoescape=False, keep_trailing_newline=True, lstrip_blocks=True, trim_blocks=True)`.
2. Para cada template: render com contexto derivado do spec (helpers em `generator._context(spec)`).
3. Para `.py`: `ast.parse(content)` — em falha, levantar `TranspilerError(code="E_TRANSPILER_SYNTAX", ...)` citando o nome do arquivo.
4. Escrever em `output_dir/generated_agent/<filename>`, ordem estável (sorted).

CLI `__main__`:
- Argumentos: `<spec_path> [-o|--output <dir>] [-v]`.
- Códigos de saída: `0` ok, `1` `E_TRANSPILER_SCHEMA`, `2` `E_TRANSPILER_RENDER`, `3` `E_TRANSPILER_SYNTAX`.
- Stderr carrega `code` + `message` + `hint` em PT-BR.

Templates referenciam literalmente:
- `from google.adk.agents import LlmAgent`
- `from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams` (ADR-0001 nota de correção, ADR-0006 nota de correção)
- `from security import pii_mask` quando `guardrails.pii.enabled=True` (ADR-0003)

## Data models

Não introduz novos; consome `AgentSpec` do Bloco 1. Contexto do Jinja2 é um `dict` derivado de `spec.model_dump(mode="json")`.

## Contratos

Saída do transpilador (forma do pacote gerado) é um contrato implícito com o Bloco 6. O shape do `agent.py` gerado segue o exemplo em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "`generated_agent`".

CLI (público):
```
python -m transpiler <spec.json> [-o <dir>] [-v]
```

## Design by Contract

Declare contratos semânticos do bloco — pré/pós/invariantes que o código deve honrar. Cada entrada vira teste correspondente em `tasks.md` § Tests.

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `render(spec, output_dir)` | `spec` é `AgentSpec` aprovada (Bloco 1); `output_dir.resolve().is_relative_to(Path.cwd())` (ADR-0008) | cada `.py` escrito passa `ast.parse`; `agent.py` ≤ 100 KB pós-render (ADR-0008); diretório populado na ordem ordenada | render é determinístico — `render(spec)` duas vezes em tmpdirs distintos produz diff zero | AC2, AC3, AC11, AC13 | T011 `[DbC]` (determinismo), T012 `[DbC]` (`ast.parse`), T033 `[DbC]` (path traversal), T035 `[DbC]` (cap 100 KB) |

**Onde declarar no código**:
- Docstring Google-style com seções `Pre`, `Post`, `Invariant`.
- Pydantic `field_validator` / `model_validator` para dados.
- `assert` em fronteiras críticas de `transpiler/` e `security/` (stdlib; sem lib extra).

**Onde enforcar**:
- Cada linha desta tabela tem teste em `tasks.md § Tests` — numeração `T0xx` ou marcado `[DbC]`.

## Dependências

| Nome | Versão mínima | Motivo | Alternativa |
|---|---|---|---|
| `jinja2` | `^3.1` | Template engine (ADR-0002) | `ast.Module(body=[...])` puro (rejeitado em ADR-0002 — verboso) |
| `pytest-regressions` | `^2` | Snapshot de outputs (GUIDELINES § 4) | Diff manual (rejeitado — frágil) |

## Riscos

| Risco | Mitigação |
|---|---|
| Diff "visual" do output flutua por whitespace entre execuções. | `trim_blocks=True`, `lstrip_blocks=True`, sorted imports, `keep_trailing_newline=True`. Snapshot tests pegam drift (AC9). |
| `McpToolset` / `StreamableHTTPConnectionParams` renomeados de novo pelo ADK. | Pin exato da versão do `google-adk` em `requirements.txt` gerado; ADR nova se quebrar (ADR-0005 prevê). |
| `ast.parse` sucede mas o código quebra em runtime por símbolo inexistente. | Bloco 6 cobre — este bloco garante só sintaxe. Teste de integração do Bloco 6 captura. |
| Diretório de saída existe com lixo. | CLI valida + opcionalmente limpa; default é abortar se `output_dir/generated_agent` já existe (evita surpresa). |

## Estratégia de validação

- **Test-first obrigatório** (ADR-0004, GUIDELINES § 4): `qa-engineer` escreve testes RED antes de qualquer linha em `generator.py` ou templates.
- **Unit tests** em `tests/transpiler/test_generator.py`: renderiza fixture → compara com snapshot → roda `ast.parse`.
- **Snapshot tests** via `pytest-regressions` para cada fixture JSON (inicial: `spec.example.json`).
- **CLI tests** em `tests/transpiler/test_cli.py`: invoca via `subprocess.run([sys.executable, "-m", "transpiler", ...])` para cobrir entry point + códigos de saída.
- **Determinismo test** (AC2): rodar render 2× em tmpdirs distintos e `assert filecmp.dircmp(a, b).diff_files == []`.
- **Cobertura**: `pytest --cov=transpiler --cov-fail-under=80`; anexado em evidência (AC10).

**Estratégia de validação atualizada (ADR-0008)**:
- **Path traversal (AC11)**: `cli.py` normaliza `output_dir` via `Path(output_dir).resolve()` e verifica `.is_relative_to(Path.cwd())` antes de criar o diretório; violação levanta `TranspilerError(code="E_TRANSPILER_RENDER")` com mensagem PT-BR "output_dir fora do projeto".
- **Template injection (AC12)**: `generator._context(spec)` aplica allow-list regex (`^[a-z0-9][a-z0-9_-]*$`) em campos que viram identifiers Python (ex.: `name`) antes de popular o contexto do Jinja2; reforço em camadas do AC3 do Bloco 1.
- **Cap pós-render (AC13)**: após `render_template(...)`, `generator` mede `len(content.encode("utf-8"))` do `agent.py`; se > 100 KB, levanta `TranspilerError(code="E_TRANSPILER_RENDER_SIZE")` citando bytes observados vs cap.
- **Shape canônico de erro**: `cli.py` usa `format_challenge_error()` (helper do Bloco 1) para serializar erros no stderr conforme ADR-0008.

## Dependências entre blocos

- **Depende do Bloco 1** em termos de **código**: importa `AgentSpec`, `TranspilerError`. Precisa estar em GREEN.
- Em termos de **spec/contrato**: Bloco 1 e Bloco 2 foram aprovados juntos no checkpoint #1 coletivo; o engenheiro pode iniciar RED enquanto Bloco 1 está em GREEN, mas GREEN do 2 precisa do 1 pronto.
- **Independente** de Blocos 3, 4, 5 no nível de spec: as URLs/base_urls que aparecem nos templates são **strings do JSON**, não imports.
- **Bloqueia** o Bloco 6 (agente): sem o pacote gerado, não há agente para executar.
