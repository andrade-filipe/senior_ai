---
id: 0003-mcp-ocr-rag
title: Servidores MCP OCR e RAG via FastMCP + SSE com mock determinístico
status: implemented
linked_requirements: [R02, R03, R11]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O agente precisa consumir dois servidores MCP: um para extrair nomes de exames de uma imagem (OCR) e outro para mapear esses nomes em códigos canônicos via RAG sobre um catálogo de ≥ 100 exames. Sem esses serviços rodando em SSE (ADR-0001), o Bloco 6 não tem fontes para consultar e o E2E (Bloco 8) é impossível.

- O que falta hoje? Dois processos Python com FastMCP expondo tools conforme assinaturas congeladas em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Assinaturas exatas das tools MCP"; um mock de OCR determinístico (R11); um catálogo CSV com ≥ 100 exames (ADR-0007).
- Quem é afetado? Agente gerado (Bloco 6), compose (Bloco 7), avaliador (interage via E2E).
- Por que importa agora? Toda a camada de **context** (nomenclatura Huyen) do agente vive aqui; também é onde aplicamos a **primeira linha** de defesa PII (ADR-0003).

## User stories

- Como **agente**, quero chamar `extract_exams_from_image(image_base64)` em SSE e receber uma lista de nomes de exames já **mascarada** de PII.
- Como **agente**, quero chamar `search_exam_code(exam_name)` e obter um `ExamMatch` (name, code, score) quando houver match acima do threshold; caso contrário `None` para acionar o modo degradado.
- Como **avaliador**, quero inspecionar o catálogo em `rag_mcp/data/exams.csv` e ver pelo menos 100 exames com header `name,code,category,aliases`.
- Como **devops-engineer**, quero que cada MCP exponha um endpoint HTTP estável (`/sse`) em porta fixa para configurar o compose.

## Critérios de aceitação

### OCR MCP

- [AC1] Dado o servidor `ocr-mcp` rodando em `:8001`, quando um cliente MCP conecta em `http://ocr-mcp:8001/sse`, então a handshake do transporte SSE completa e a tool `extract_exams_from_image` aparece no inventory.
- [AC2] Dado um `image_base64` correspondente a uma fixture conhecida, quando a tool é chamada, então retorna uma **lista determinística** de nomes de exames (ex.: `["Hemograma Completo", "Glicemia de Jejum"]`) — mesmo hash → mesma lista (R11).
- [AC3] Dado um `image_base64` **novo** (não-fixture), quando a tool é chamada, então retorna uma lista (pode ser vazia) sem levantar exceção não-tratada; texto de fallback também passa pelo `pii_mask` antes de retornar.
- [AC4] Dado qualquer retorno da tool OCR, quando inspecionado, então **nenhum token corresponde** a um valor cru detectado como PII pelas classes de entidade listadas em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII" — a saída já passou por `security.pii_mask` (ADR-0003).

### RAG MCP

- [AC5] Dado o servidor `rag-mcp` rodando em `:8002`, quando um cliente conecta em `http://rag-mcp:8002/sse`, então a handshake completa e as tools `search_exam_code` e `list_exams` aparecem no inventory.
- [AC6] Dado o arquivo `rag_mcp/data/exams.csv` carregado no startup, quando inspecionado, então contém ≥ 100 linhas de dados + header com colunas `name,code,category,aliases` nessa ordem (R03, ADR-0007).
- [AC7] Dado uma query exata existente no catálogo (ex.: `"Hemograma Completo"`), quando `search_exam_code` é chamada, então retorna `ExamMatch(name, code, score>=0.95)`.
- [AC8] Dado uma query com typo leve (ex.: `"Hemograma Complet"`), quando `search_exam_code` é chamada e o score do melhor match ≥ 80 (escala rapidfuzz), então retorna `ExamMatch` correspondente; caso contrário retorna `None`.
- [AC9] Dado uma query correspondente a um alias no CSV (ex.: `"HMG"`), quando `search_exam_code` é chamada, então retorna o `ExamMatch` apontando para o `code` canônico do registro pai.
- [AC10] Dado o catálogo carregado, quando `list_exams(limit=5)` é chamada, então retorna exatamente 5 `ExamSummary(name, code)` na ordem do CSV.

### Infra comum

- [AC11] Cada MCP loga em JSON estruturado ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Formato de log"), com `service`, `event`, `correlation_id` (quando disponível via metadata MCP) e sem PII crua.
- [AC12] Cada MCP aceita healthcheck via `HEAD http://<host>:<port>/sse` retornando 200 ou 405 — suficiente para `service_started` no compose (ADR-0001).
- [AC13] Dado que `search_exam_code` retorna um `ExamMatch`, quando o campo `score` é inspecionado, então é um `float` normalizado em `[0.0, 1.0]` — nunca `None` dentro de um `ExamMatch`, nunca fora do intervalo. `None` como retorno da tool indica **ausência de match** (abaixo do threshold 80/100 em escala rapidfuzz), nunca score inválido.
- [AC14] Dado `rag_mcp/data/exams.csv` (ou qualquer CSV passado a `catalog.load(path)`) com `code` duplicado entre linhas, quando `catalog.load` roda, então levanta exceção (ex.: `CatalogError`) que identifica a **linha** e o **valor** duplicado (ex.: `CatalogError: duplicate code 'B2' at line 47`). Invariante `code` único em todo o catálogo.
- [AC15] Dado um `image_base64` > 5 MB (após decode), quando `extract_exams_from_image` é chamada, então levanta `ToolError(code="E_OCR_IMAGE_TOO_LARGE")` com mensagem citando bytes observados vs cap conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md); não processa a imagem.
- [AC16] Dado um `image_base64` inválido (string não-base64, vazia, ou decode falha), quando `extract_exams_from_image` é chamada, então levanta `ToolError(code="E_OCR_INVALID_INPUT")` com `hint` em PT-BR sugerindo verificar encoding; não tenta hashear.
- [AC17] Dado que o lookup/processamento do OCR excede 5 segundos (improvável no mock, mas enforced por contrato), quando a tool roda, então levanta `ToolError(code="E_OCR_TIMEOUT")` conforme [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md).
- [AC18] Dado um `exam_name` > 500 chars, quando `search_exam_code` é chamada, então levanta `ToolError(code="E_RAG_QUERY_TOO_LARGE")` citando o cap; não invoca `rapidfuzz`.
- [AC19] Dado um `exam_name` vazio ou apenas whitespace (após `strip()`), quando `search_exam_code` é chamada, então levanta `ToolError(code="E_RAG_QUERY_EMPTY")` com `hint` em PT-BR; não invoca `rapidfuzz`.
- [AC20] Dado que `catalog.load(path)` falha (arquivo ausente, header inválido, `code` duplicado ou CSV malformado), quando o servidor sobe, então o startup aborta com `CatalogError(code="E_CATALOG_LOAD_FAILED")` conforme shape canônico de ADR-0008 (linha única JSON em stderr com `code`, `message`, `hint`, `path`, `context`); processo termina com exit ≠ 0.
- [AC21] Dado que o processamento de `search_exam_code` excede 2 segundos, quando a tool roda, então levanta `ToolError(code="E_RAG_TIMEOUT")` conforme [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md).

## Robustez e guardrails

### Happy Path

Cliente MCP conecta em `ocr-mcp:8001/sse` → chama `extract_exams_from_image(<png base64 de 200 KB>)` → retorna `["Hemograma Completo", ...]` já mascarado em < 100 ms. Cliente conecta em `rag-mcp:8002/sse` → chama `search_exam_code("Hemograma Completo")` → retorna `ExamMatch(name, code, score=0.99)` em < 50 ms.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| `image_base64` > 5 MB após decode | rejeitar antes de hash | `E_OCR_IMAGE_TOO_LARGE` | AC15 |
| `image_base64` inválido (decode falha) | rejeitar antes de processar | `E_OCR_INVALID_INPUT` | AC16 |
| OCR excede 5s | timeout hard | `E_OCR_TIMEOUT` | AC17 |
| `exam_name` > 500 chars | rejeitar antes de `rapidfuzz` | `E_RAG_QUERY_TOO_LARGE` | AC18 |
| `exam_name` vazio/whitespace | rejeitar com hint | `E_RAG_QUERY_EMPTY` | AC19 |
| CSV ausente/malformado no startup | aborta processo | `E_CATALOG_LOAD_FAILED` | AC20 |
| RAG excede 2s | timeout hard | `E_RAG_TIMEOUT` | AC21 |
| `code` duplicado no CSV | `CatalogError` cita linha | `E_CATALOG_LOAD_FAILED` | AC14, AC20 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| `image_base64` (bytes decodificados) | 5 MB | `E_OCR_IMAGE_TOO_LARGE` | AC15 |
| `extract_exams_from_image` (timeout) | 5 s | `E_OCR_TIMEOUT` | AC17 |
| `exam_name` (chars) | 500 | `E_RAG_QUERY_TOO_LARGE` | AC18 |
| `search_exam_code` (timeout) | 2 s | `E_RAG_TIMEOUT` | AC21 |

### Security & threats

- **Ameaça**: cliente malicioso envia imagem de 50 MB e derruba o processo OCR via esgotamento de memória.
  **Mitigação**: cap de 5 MB após decode (AC15); fail-fast antes de chamar `sha256`.
- **Ameaça**: cliente envia query com 10 MB de texto e trava o `rapidfuzz` num loop de comparação quadrática.
  **Mitigação**: cap de 500 chars em `exam_name` (AC18); empty-guard antes (AC19).
- **Ameaça**: CSV corrompido em deploy coloca o RAG num estado onde retorna códigos falsos.
  **Mitigação**: `catalog.load` valida no startup; duplicatas abortam (AC14, AC20); processo termina e compose reporta falha — sem silent degradation.

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC4 | `extract_exams_from_image(image_base64)` | Post (PII linha 1) |
| AC6, AC14 | `catalog.load(path)` | Invariant (unique code, ≥ 100 entries) |
| AC7, AC8, AC13 | `search_exam_code(exam_name)` | Post |
| AC15, AC16, AC17 | `extract_exams_from_image(image_base64)` | Pre (image size, base64 valid) + Post (timeout) |
| AC18, AC19, AC21 | `search_exam_code(exam_name)` | Pre (query size, non-empty) + Post (timeout) |
| AC20 | `catalog.load(path)` | Post (shape canônico de erro ADR-0008) |

## Requisitos não-funcionais

- **Transporte**: SSE no servidor (ADR-0001), via `mcp.run(transport="sse", host="0.0.0.0", port=...)`.
- **Mock determinístico** do OCR: hash da imagem → texto canned em um dicionário fixture (R11).
- **Latência** das tools: p95 < 100 ms para OCR (mock) e < 50 ms para RAG (rapidfuzz) em dev local; apenas inspeção manual no Bloco 8.
- **Observabilidade**: `event=tool.called` e `event=tool.failed` com `duration_ms`.
- **PII**: OCR aplica `security.pii_mask` antes de retornar; função exportada pelo Bloco 5 (ADR-0003).

## Clarifications

*(nenhuma — stub identity oficial de `pii_mask` é exposto pelo Bloco 5 (T001) desde o dia zero; Bloco 3 importa `from security import pii_mask` diretamente, sem stub temporário local.)*

## Fora de escopo

- OCR real (Tesseract, Google Vision). R11 aceita mock determinístico no MVP.
- Re-ranking ou embeddings no RAG (ADR-0007 rejeita explicitamente).
- Autenticação nos MCPs (rede interna do compose).
- Persistência de chamadas a tools (apenas logs de evento).
