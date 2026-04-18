# ADR-0008: Robustez de validação — taxonomia de erros, guardrails e shape de resposta

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

Duas auditorias pré-implementação (lacunas por bloco + catálogo de requisitos transversais) mostraram que a política de validação está **fragmentada**:

- Cada bloco tende a inventar seus próprios códigos `E_*` sem uma tabela consolidada (ex.: `PIIError(code="E_PII_LANGUAGE")` em `security/`, `TranspilerError(code="E_TRANSPILER_SCHEMA")` em `transpiler/`, `E_RAG_NO_MATCH` em `docs/ARCHITECTURE.md` § "Taxonomia de erros"). Faltam `E_OCR_TIMEOUT`, `E_OCR_IMAGE_TOO_LARGE`, `E_PII_TEXT_SIZE`, `E_AGENT_TIMEOUT`, entre outros.
- **Limites de tamanho não existem** em entradas críticas — nem `image_base64` (OCR), nem `text` (`pii_mask`), nem `exams[]` (API), nem `mcp_servers[]` (schema). Vetor de DoS trivial.
- **Timeouts de falha** nunca foram declarados com código de erro — só há menção de latência p95 como métrica não-funcional. Resultado: um bloco pode travar silenciosamente sem sinalizar ao chamador.
- **Shape da resposta de erro** foi descrito como "mensagem Pydantic com campo + motivo" (ARCHITECTURE) — sem exemplo JSON canônico, cada bloco serializa `ChallengeError` do seu jeito.
- `correlation_id` e "nenhum log com PII" são GUIDELINES soltas, **não critérios testáveis** hoje.

O desafio é explícito sobre robustez ([DESAFIO](../DESAFIO.md): *"o transpilador precisa ser robusto: deve validar os inputs"*), mas o princípio ficou restrito ao transpilador quando na verdade atinge toda a superfície externa do sistema (OCR, RAG, API, PII guard, agente, compose, E2E).

Esta ADR centraliza a política como **contrato cross-service** — caps, timeouts e formato de erro passam a viver em uma fonte da verdade única (aqui + tabelas concretas em `docs/ARCHITECTURE.md § Robustez e guardrails`) e cada bloco referencia.

## Alternativas consideradas

1. **Deixar cada bloco definir sua taxonomia `E_*`** (estado anterior, implícito).
   - Prós: menos governança; velocidade local alta.
   - Contras: drift garantido; impossível para `code-reviewer` validar mecanicamente; chamador do agente nunca sabe se trata `E_TIMEOUT` ou `E_MCP_TIMEOUT`.
   - **Rejeitada**.

2. **Adotar RFC 7807 (Problem Details for HTTP APIs)** como shape oficial.
   - Prós: padrão público reconhecido; suporte em toolchains (FastAPI, Spring).
   - Contras: nosso stack é uniforme Pydantic + CLI + logs JSON; shape próprio — alinhado a `ChallengeError(code, message, hint)` — cobre o essencial com zero dependência extra; RFC 7807 adiciona campos (`type`, `title`, `instance`) que não agregam aqui.
   - **Considerada mas não adotada**. Fica como evolução futura se virar fricção de integração.

3. **Usar lib pronta (ex.: `pydantic-exceptions`, `flask-problem`)**.
   - Prós: funcionalidade pronta.
   - Contras: overhead de dependência para ganho marginal; nossa base `ChallengeError` já existe.
   - **Rejeitada**.

4. **Política cross-cutting centralizada em ADR + ARCHITECTURE (escolhida)**.
   - Prós: fonte única da verdade; `code-reviewer` valida mecanicamente; cada bloco herda; extensões futuras exigem PR atualizando esta ADR — nunca surpresa em produção.

## Decisão

Esta ADR congela seis contratos cross-service. `docs/ARCHITECTURE.md § Robustez e guardrails` instancia as mesmas tabelas com detalhe operacional; divergência entre os dois arquivos é bug de processo e resolve-se atualizando **primeiro** esta ADR.

### 1. Taxonomia `E_*` é imutável e centralizada

Todos os códigos `E_*` usados por qualquer bloco vivem na tabela consolidada de `docs/ARCHITECTURE.md § Robustez e guardrails § Códigos de erro`. A tabela traz, para cada código: **módulo dono**, **condição disparadora**, **mensagem canônica ao usuário (PT-BR)** e **hint de correção**. Reuso entre módulos é proibido. **Novos códigos exigem PR que atualize a tabela antes do uso em código** — `code-reviewer` rejeita commits que introduzam `E_*` fora da tabela.

### 2. Shape de resposta de erro canônica

Toda exceção que herda de `ChallengeError` serializa para o envelope:

```json
{
  "code": "E_API_VALIDATION",
  "message": "patient_ref inválido",
  "hint": "Use padrão ^anon-[a-z0-9]+$",
  "path": "body.patient_ref",
  "context": {"received": "João Silva", "expected_pattern": "^anon-..."}
}
```

Variantes por transporte (mesmos campos, wrapper adicional):

- **HTTP** (FastAPI): `{"error": {<shape acima>}, "correlation_id": "<uuid>"}` no body; status ≠ 2xx.
- **CLI** (transpilador, agente): uma linha por campo em stderr, `code` primeiro; exit code ≠ 0 por categoria (1 schema, 2 render, 3 syntax, etc.).
- **Log JSON**: shape acima + `timestamp`, `service`, `correlation_id`, `event=error.raised`.

Campos `path` e `context` são **opcionais** mas fortemente recomendados. `hint` é obrigatório quando o usuário consegue agir (ex.: formato esperado, serviço a reiniciar). `context` **nunca** contém PII crua — apenas entity_type, expected_pattern, sha256_prefix, métricas.

### 3. Guardrails de tamanho (caps como contrato)

| Alvo | Cap | Código em violação |
|---|---|---|
| `image_base64` decoded | 5 MB | `E_OCR_IMAGE_TOO_LARGE` |
| `text` em `pii_mask` | 100 KB | `E_PII_TEXT_SIZE` |
| `exam_name` query RAG | 500 chars | `E_RAG_QUERY_TOO_LARGE` |
| `mcp_servers[]` (spec) | 10 itens | `E_TRANSPILER_SCHEMA` |
| `http_tools[]` (spec) | 20 itens | `E_TRANSPILER_SCHEMA` |
| `tool_filter[]` (spec) | 50 itens | `E_TRANSPILER_SCHEMA` |
| `name`, `description`, `instruction` (strings do spec) | 500 chars | `E_TRANSPILER_SCHEMA` |
| URL em `url`, `base_url`, `openapi_url` | 2048 chars | `E_TRANSPILER_SCHEMA` |
| `patient_ref` (API) | 64 chars | `E_API_VALIDATION` |
| `exams[]` no POST | 20 itens | `E_API_VALIDATION` |
| `spec.json` total (bytes do arquivo) | 1 MB | `E_TRANSPILER_SCHEMA` |
| `agent.py` gerado | 100 KB | `E_TRANSPILER_RENDER_SIZE` |
| HTTP body POST | 10 MB (default FastAPI) | 413 Payload Too Large |
| `allow_list` (PII) | 1000 itens | `E_PII_ALLOW_LIST_SIZE` |

Caps são checados na **borda** (antes de processar): o `text` grande **não deve** chegar ao Presidio; o `image_base64` inválido **não deve** chegar ao base64-decoder; o `spec.json` grande **não deve** chegar ao `json.loads`.

### 4. Timeouts de falha

| Operação | Timeout | Código em violação |
|---|---|---|
| OCR tool call (`extract_exams_from_image`) | 5 s | `E_OCR_TIMEOUT` |
| RAG tool call (`search_exam_code`, `list_exams`) | 2 s | `E_RAG_TIMEOUT` |
| POST `/api/v1/appointments` | 10 s | `E_API_TIMEOUT` |
| Agente total (execução CLI) | 300 s (5 min) | `E_AGENT_TIMEOUT` |
| Healthcheck HTTP (compose) | 30 s total | timeout do compose |
| Retry MCP (policy já em ADR-0006) | delay fixo 500 ms, 1 tentativa | — |

Timeout não é sinônimo de latência p95. p95 é métrica de observabilidade (NFR); timeout é **contrato de falha** — se passar, levanta `E_*_TIMEOUT` com `hint` para o chamador. Os dois coexistem.

### 5. Correlation ID

- **Origem**: a CLI do agente gera um UUID v4 no início da execução.
- **Propagação HTTP**: via header `X-Correlation-ID` em todas as chamadas (OCR, RAG, API).
- **Propagação MCP**: via metadata/contexto quando disponível; fallback local `mcp-<uuid4>[:8]`.
- **Eco**: `scheduling-api` devolve o header no response (gerando `api-<uuid4>[:8]` se ausente na request).
- **Logs**: 100 % dos registros JSON têm o campo `correlation_id`. Auditável por script simples: `jq 'select(.correlation_id == null)' logs/*.json` deve retornar vazio.

### 6. Logging sem PII crua

Nenhum log emite valor cru detectado como entidade PII. O formato permitido para referenciar um dado mascarado é:

```json
{"entity_type": "BR_CPF", "sha256_prefix": "a1b2c3d4", "score": 0.95}
```

Auditável por evidência: E2E grep em todos os arquivos sob `docs/EVIDENCE/` por fixtures conhecidas (CPF, nome) retorna zero matches (Bloco 0008 AC15).

## Consequências

**Positivas**:

- **Rastreabilidade mecânica**: `code-reviewer` ganha checklist "taxonomia `E_*` conforme ADR-0008"; grep por código de erro em produção sempre resolve para uma linha da tabela.
- **Superfície de ataque reduzida**: caps + timeouts previnem vetores triviais de DoS (base64 enorme, regex em texto de 10 MB, loop sem timeout).
- **UX acionável**: shape canônico garante que qualquer ferramenta downstream (Swagger, CLI do avaliador, logs) ofereça mensagem + hint + path consistentes.
- **Correlation ID auditável**: passa de diretriz solta para critério testável (presente em AC de 0004 e 0006).

**Negativas / débito técnico**:

- Editar caps/timeouts exige PR nesta ADR — processo mais pesado que "change a magic number".
- RFC 7807 fica como possível migração futura se integração externa exigir; nosso shape é próprio hoje.
- Aumento de escopo: 20 ACs novos nas specs (P1), distribuídos pelos 8 blocos. Estimativa de ~34 testes novos.

**Impacto em outros subsistemas**:

- Todos os 8 plans (`docs/specs/0001..0008/plan.md`) passam a referenciar esta ADR em sua seção de validação.
- Template de `spec.md` ganha seção **"Robustez e guardrails"** (Happy Path + Edge cases + Guardrails + Security & threats) — mudança aditiva em `docs/specs/README.md`.
- `code-reviewer` ganha bullet sobre códigos `E_*` pertencerem à tabela centralizada e sobre guardrails respeitados (CHANGES/BLOCKED por gravidade).
- `ai-context/GUIDELINES.md § 2` e `§ 3` ganham ponteiros para esta ADR e para a tabela de `docs/ARCHITECTURE.md`.

## Referências

- `docs/DESAFIO.md` — exigência de robustez: "o transpilador precisa ser robusto: deve validar os inputs".
- `docs/ARCHITECTURE.md § Robustez e guardrails` — tabelas concretas (instantiação desta ADR).
- `docs/ARCHITECTURE.md § Taxonomia de erros` — tabela consolidada de `E_*`.
- `docs/adr/0003-pii-double-layer.md` — PII dupla camada (linha 1 no OCR, linha 2 no `before_model_callback`); complementar a esta ADR.
- `docs/adr/0004-sdd-tdd-workflow.md` — SDD+TDD; esta ADR é consistente com edições aditivas em specs `approved`.
- `docs/adr/0006-spec-schema-and-agent-topology.md` — schema `AgentSpec`; caps citados aqui operam sobre seus campos.
- `ai-context/GUIDELINES.md § 2 Validação e erros` e `§ 3 Segurança` — operacionalização local dos princípios desta ADR.
- RFC 7807 — Problem Details for HTTP APIs (comparação; não adotado).
