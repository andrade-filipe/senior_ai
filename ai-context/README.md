# ai-context/

Este diretório é **contexto de trabalho para a IA** que desenvolve o projeto. Não é parte da entrega formal ao avaliador — os entregáveis ficam em `docs/`.

## O que entra aqui

- **`GUIDELINES.md`** — padrões operacionais de engenharia (código, testes, segurança, git).
- **`WORKFLOW.md`** — ciclo iterativo seguido entre marcos e a regra humano-vs-IA para documentação.
- **`STATUS.md`** — quadro vivo de progresso por bloco de trabalho.
- **`references/`** — notas técnicas consolidadas durante a pesquisa (ADK, MCP-SSE, FastAPI, PII, Transpiler). São resumos para contextualizar subagentes rapidamente; **não substituem** a documentação oficial.
- **`LINKS.md`** — log vivo de **toda** fonte externa consultada (docs oficiais, blogs, codelabs, RFCs). Toda informação externa que entra no repo tem que aparecer aqui, organizada por área.

## O que **não** entra aqui

- Arquitetura oficial do sistema → `docs/ARCHITECTURE.md`.
- Decisões arquiteturais (ADRs) → `docs/adr/`.
- Evidências de funcionamento → `docs/EVIDENCE/`.
- Transcrição do desafio → `docs/DESAFIO.md`.
- Código, schemas, templates, Dockerfiles → módulos próprios (`transpiler/`, `ocr_mcp/`, …).

## Convenções

- Idioma: português para textos narrativos; inglês para identificadores e trechos de código.
- Mutável: referências técnicas podem evoluir livremente conforme aprendemos durante a implementação.
- Auditável: qualquer decisão *irreversível* sai daqui e vira ADR em `docs/adr/`.

## Relação com `CLAUDE.md`

`CLAUDE.md` (raiz) é carregado automaticamente pelo Claude Code e aponta para os arquivos deste diretório. Se você é humano navegando o repo: leia primeiro `docs/README.md` — ele é a porta de entrada oficial.
