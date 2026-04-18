# docs/ — Documentação da Entrega

Bem-vindo. Este diretório contém os **entregáveis de documentação** do desafio técnico. Aqui você encontra o que precisa para avaliar a solução.

## Índice

| Arquivo | Finalidade |
|---|---|
| [`DESAFIO.md`](./DESAFIO.md) | Transcrição fiel do PDF do desafio (fonte da verdade para requisitos). |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Arquitetura-alvo: serviços, contratos entre componentes, diagramas (mermaid), variáveis de ambiente. |
| [`adr/`](./adr/) | Registros de decisões arquiteturais (ADRs) aceitas durante o desenvolvimento, em ordem cronológica. |
| [`EVIDENCE/`](./EVIDENCE/) | Evidências de funcionamento por marco: logs, capturas do Swagger, transcrições da CLI. |

## Onde está o resto?

- **Como rodar a solução**, quickstart, stack, dependências → `README.md` na raiz do repositório.
- **Processo de desenvolvimento** (fluxo de trabalho, padrões de código, uso de IA) → `ai-context/` (contexto interno de trabalho; exposto para transparência).
- **Código-fonte** → módulos próprios na raiz (`transpiler/`, `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, `security/`, `generated_agent/`).

## Convenções

- Este diretório é em **português**, pensado para leitores brasileiros.
- Conteúdo aqui é **estável**: só muda quando a arquitetura ou um contrato muda.
- ADRs são **imutáveis** após aceite; mudanças geram nova ADR que *supersede* a anterior.
