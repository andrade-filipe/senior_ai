# docs/ — Documentação da Entrega

Bem-vindo. Este diretório contém os **entregáveis de documentação** do desafio técnico. Aqui você encontra o que precisa para avaliar a solução.

## Índice

| Arquivo | Finalidade |
|---|---|
| [`DESAFIO.md`](./DESAFIO.md) | Transcrição fiel do PDF do desafio (fonte da verdade para requisitos). |
| [`REQUIREMENTS.md`](./REQUIREMENTS.md) | Requisitos R01..Rn com IDs estáveis; cada spec cita quais requisitos endereça. |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Arquitetura-alvo: serviços, contratos entre componentes, diagramas (mermaid), variáveis de ambiente. |
| [`WALKTHROUGH.md`](./WALKTHROUGH.md) | Narrativa técnica ponta a ponta — o que acontece quando você roda o agente (OCR → PII → LLM → RAG → API). |
| [`REFERENCES.md`](./REFERENCES.md) | Principais referências externas consultadas (fontes primárias) agrupadas por domínio e ancoradas nas ADRs. |
| [`tutorials/`](./tutorials/README.md) | Tutoriais por funcionalidade (transpilador, OCR MCP, RAG MCP, API, agente, PII guard) com comandos concretos e troubleshooting. |
| [`runbooks/e2e-manual-gemini.md`](./runbooks/e2e-manual-gemini.md) | Runbook completo do E2E manual com Gemini real (T021 — responsabilidade do avaliador). |
| [`adr/`](./adr/) | Registros de decisões arquiteturais (ADRs) aceitas durante o desenvolvimento, em ordem cronológica. |
| [`specs/`](./specs/) | Specs SDD (`spec.md` / `plan.md` / `tasks.md`) por bloco — o artefato primário do processo. |
| [`EVIDENCE/`](./EVIDENCE/) | Evidências de funcionamento por marco: logs, capturas do Swagger, transcrições da CLI. |

## Onde está o resto?

- **Como rodar a solução**, quickstart, stack, dependências → `README.md` na raiz do repositório.
- **Processo de desenvolvimento** (fluxo de trabalho, padrões de código, uso de IA) → `ai-context/` (contexto interno de trabalho; exposto para transparência).
- **Código-fonte** → módulos próprios na raiz (`transpiler/`, `ocr_mcp/`, `rag_mcp/`, `scheduling_api/`, `security/`, `generated_agent/`).

## Convenções

- Este diretório é em **português**, pensado para leitores brasileiros.
- Conteúdo aqui é **estável**: só muda quando a arquitetura ou um contrato muda.
- ADRs são **imutáveis** após aceite; mudanças geram nova ADR que *supersede* a anterior.
