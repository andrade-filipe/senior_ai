# ADR-0002: Transpilador JSON → Python via Jinja2 + `ast.parse`

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

O coração do desafio é um **transpilador** que, dado um `spec.json` validado, produz um pacote Python com um agente ADK funcional (`generated_agent/`). A saída precisa ser **código Python válido, idiomático e estável entre execuções** (mesmo input → mesmo output byte-a-byte).

Há duas estratégias clássicas:
1. **Templates textuais** (Jinja2, Mako, string.Template).
2. **AST-builder programático** (`ast.Module(...)` diretamente, ou `libcst`).

Precisamos decidir agora antes de qualquer código do transpilador.

## Alternativas consideradas

1. **Jinja2 + `ast.parse` como gate (escolhido)** — um template por "tipo de arquivo gerado" (`agent.py.j2`, `__init__.py.j2`, `requirements.txt.j2`, `Dockerfile.j2`, `.env.example.j2`). Após render, rodar `ast.parse()` em cada `.py` emitido; se falhar, falha a build do transpilador com erro acionável.
   - Prós: templates legíveis, diff amigável quando o formato muda, `ast.parse` garante que nunca emitimos Python inválido.
   - Contras: templates textuais podem gerar código não idiomático (ex.: indentação torta) se não cuidarmos. Mitigação: rodar `ruff format` no output como passo final opcional.

2. **AST-builder puro (`ast.Module(body=[...])`)** — construir a árvore AST e usar `ast.unparse()`.
   - Prós: impossível gerar Python inválido por construção; tipagem forte.
   - Contras: verboso para código trivial; diff ilegível quando a forma do output evolui; `ast.unparse()` perde fidelidade estilística (quebra de linha, whitespace).

3. **`libcst` (Concrete Syntax Tree)** — preserva trivia (whitespace, comments).
   - Prós: fidelidade estilística.
   - Contras: dependência pesada para um transpilador pequeno; curva de aprendizado; overkill.

## Decisão

Transpilador implementado como **Jinja2 + `ast.parse` final**. Fluxo:

1. Ler `spec.json` → validar com `AgentSpec` (Pydantic v2).
2. Carregar templates de `transpiler/templates/*.j2`.
3. Renderizar cada template com o contexto do spec.
4. Para cada `.py` gerado: `ast.parse(content)` — falha dura se inválido.
5. Escrever em `<output>/generated_agent/`.

`ruff format` no output **não** é obrigatório no MVP (complexidade extra); se o diff ficar feio depois, abrimos ADR.

## Consequências

- **Positivas**: legibilidade alta dos templates; separação limpa entre "forma" (template) e "dados" (spec); `ast.parse` é garantia formal de correção sintática.
- **Negativas**: templates precisam de disciplina com whitespace; snapshots dos outputs (pytest-regressions) detectam regressões visuais cedo.
- **Impacto**: `transpiler-engineer` trabalha com `templates/` + `generator.py`; `qa-engineer` cria snapshots para cada fixture JSON.

## Referências

- `ai-context/references/TRANSPILER.md`
- https://jinja.palletsprojects.com/en/3.1.x/
- https://docs.python.org/3/library/ast.html
- https://pypi.org/project/pytest-regressions/
