# Tutoriais por funcionalidade

Guias práticos de leitura focada, um por subsistema. Cada tutorial é independente: assume apenas que você clonou o repositório e tem Docker + `uv` instalados. Quando um tutorial depende de outro serviço estar de pé, ele diz explicitamente qual `docker compose up` rodar antes.

Todos seguem a mesma estrutura — **Objetivo**, **Pré-requisitos**, **Como invocar**, **Contratos resumidos**, **Exemplos completos**, **Troubleshooting**, **Onde estender** — para reduzir carga cognitiva entre subsistemas.

## Índice

| # | Tutorial | Quando usar |
|---|---|---|
| 01 | [Transpiler CLI](./01-transpiler-cli.md) | Escrever um `spec.json`, rodar o transpilador e inspecionar o pacote `generated_agent/` emitido. |
| 02 | [OCR MCP](./02-ocr-mcp.md) | Chamar a tool `extract_exams_from_image` via SSE; entender o mock determinístico e a camada PII embutida. |
| 03 | [RAG MCP](./03-rag-mcp.md) | Chamar `search_exam_code` / `list_exams`; entender o scoring do rapidfuzz; **adicionar um exame novo** ao catálogo CSV. |
| 04 | [Scheduling API](./04-scheduling-api.md) | Criar/listar/buscar agendamentos via Swagger ou `curl`; observar erros canônicos e o `correlation_id` nos logs. |
| 05 | [Generated Agent](./05-generated-agent.md) | Rodar o agente ADK gerado ponta a ponta; entender o fluxo interno (OCR → RAG → API) e variáveis de ambiente relevantes. |
| 06 | [PII Guard](./06-pii-guard.md) | Usar `pii_mask` contra texto com PII brasileiro; adicionar entidade nova; ajustar `allow_list`. |

## Relação com outros documentos

- **Arquitetura estática** (serviços, portas, contratos formais): [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md).
- **Narrativa de execução ponta a ponta** (o que acontece quando o agente roda): [`docs/WALKTHROUGH.md`](../WALKTHROUGH.md).
- **Runbook manual do E2E com Gemini real** (T021 — responsabilidade do avaliador): [`docs/runbooks/e2e-manual-gemini.md`](../runbooks/e2e-manual-gemini.md).
- **Decisões arquiteturais** que justificam cada subsistema: [`docs/adr/`](../adr/).
- **Evidências de funcionamento** por marco (logs, comandos reproduzíveis): [`docs/EVIDENCE/`](../EVIDENCE/).

Voltar para o índice geral: [`docs/README.md`](../README.md).
