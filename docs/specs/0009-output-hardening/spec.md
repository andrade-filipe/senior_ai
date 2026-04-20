---
id: 0009-output-hardening
title: Output hardening — fixture reliability, tolerant schema e validator-pass
status: implemented
linked_requirements: [R05, R08, R11]
owner_agent: software-architect
created: 2026-04-20
approved: 2026-04-20
implemented: 2026-04-21
partially_superseded_by: 0010-pre-ocr-invocation   # Camada A apenas — ver addendum abaixo
---

## Atualização 2026-04-20 — Camada A partialmente superseded por 0010

Após a instrumentação do log `ocr.lookup.hash` (T041) e a primeira execução E2E, a evidência mostrou que o Gemini **não reencaminha** os bytes de `inline_data` como argumento `image_base64` da tool — ele fabrica PNGs mínimos alucinados (184 e 223 bytes em dois turnos, sha256 variando a cada run). A causa é arquitetural (SDK `google-genai` não expõe primitiva que referencie inline_data dentro de function-call), e não é corrigível no dict `FIXTURES` do OCR-MCP.

Consequência:

- **Camada A** (fixture reliability — AC1/AC2 desta spec) fica **partialmente superseded** por [spec 0010 `pre-ocr-invocation`](../0010-pre-ocr-invocation/spec.md) e por [ADR-0010](../../adr/0010-preocr-invocation-pattern.md). A abordagem passa a ser **pré-OCR no CLI**: a CLI chama `extract_exams_from_image` via MCP-SSE client antes de `runner.run_async` e injeta a lista de exames no prompt como texto. `register_fixture` (T040) permanece implementado como API pública útil.
- **Camada B** (`RunnerSuccess | RunnerError` com discriminador) continua válida e é implementada conforme planejado — o agente ainda pode falhar em RAG/scheduling mesmo com OCR correto.
- **Camada C** (validator-pass opcional via `google.genai` direto) continua válida.

Tarefas afetadas em `tasks.md`: T010, T011, T012, T042 passam a `deferred (superseded by 0010)`. T013 e T041 permanecem `done` (o log é o que permitiu diagnosticar o problema). T050–T063 (Camadas B e C) permanecem ativas.

---

## Atualização 2026-04-21 — Camada D (prompt hardening) + fence stripping

Evidência do E2E 2026-04-20 com `gemini-2.5-pro` (logs `20ea3e34-d4d6-…`): todo o pipeline determinístico funcionou (Tesseract extraiu 4 linhas, RAG absorveu typos `Hemegrama→Hemograma 0.94`, PII mascarou endereço como `<LOCATION>`, API aceitou `apt-77bacbaf35e5` após 3 retries de data). **Falha única na última barreira**: o modelo embrulhou o JSON canônico em cerca markdown ``` ```json…``` ``` apesar da instrução "Nao use \`\`\`json". `_parse_runner_output` chamou `json.loads(text)` direto e explodiu com `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` → `E_AGENT_OUTPUT_INVALID` exit 3.

Comportamento conhecido do Gemini 2.5 Pro sob reasoning: ignora consistentemente a instrução "sem cercas" em ~30% das respostas com schema estruturado. Camada B (parser tolerante) **tem** que incluir fence stripping — senão o E2E nunca passa com Pro. Camada C (validator-pass) vira rede de segurança real em vez de feature opcional.

Novas tarefas desta fase de fechamento:

- **Camada B reforçada**: `_strip_json_fence(raw)` aplicado antes de `json.loads`. Remove ``` ```json ```, ``` ``` ```, e espaços em volta. Implementado em função pura testável.
- **Camada D — Prompt hardening** (antes fora de escopo, agora incluído a pedido do usuário):
  - Schema da resposta ganha discriminador `status` (alinhado com Camada B).
  - Regra explícita de data futura: `scheduled_for` >= `hoje + 48h`, com exemplo concreto.
  - Regra de higiene da lista de exames: ignorar itens que começam com `<` (placeholders de PII) ou `[` (bullets).
  - **CLI pré-filtra** a lista antes de montar o prompt: drop de `<PII>` placeholders + strip de prefixos `^\d+[.)\s]+` e `^[a-z][).\s]+` que o Tesseract deixa vazar.

Tarefas afetadas em `tasks.md`: novas T080–T086 para Camada D. T053 (update do `spec.example.json`) absorve as mudanças de prompt. T050–T052 (Camada B) permanecem, mas T050 ganha `_strip_json_fence` como sub-tarefa obrigatória.

---

## Problema

No E2E real executado em 2026-04-20 (após concluir ADR-0009, com `gemini-2.5-flash-lite` em `.env`) o agente termina sem a saída canônica. O DEBUG log mostra três falhas compostas:

1. **OCR devolve `[]` para a fixture canônica** (`docs/fixtures/sample_medical_order.png`, sha256 prefix `17c46fa5`). O Dockerfile copia o PNG para dentro do container OCR e `_get_fixture_hash()` calcula o hash desse arquivo — então as duas cópias têm o mesmo digest em disco. Ainda assim `lookup()` retorna vazio. Hipótese: o base64 que o modelo envia ao tool **não é o mesmo stream binário** da `inline_data`; Gemini pode transcodificar o `Part.from_bytes` antes de repassá-lo como argumento da função — e o hash diverge. Precisamos confirmar com teste dirigido.
2. **Modelo viola o contrato de saída sob pressão**. Após o OCR vazio, o agente repete OCR (proibido por `NAO repita esta chamada`), depois faz `POST /api/v1/appointments` com `exams=[]`, leva `422` e, em vez de abortar com o envelope de erro, inventa um schema próprio (`{"error_code","description","root_cause"}`) dentro de ` ```json ` fences. A CLI remove as fences (`_strip_json_fence` funciona), mas o JSON extraído não satisfaz `_RunnerOutput` → `E_AGENT_OUTPUT_INVALID`, exit 3.
3. **Parser da CLI é rígido**. `_RunnerOutput` aceita **apenas** a forma feliz (`exams`, `appointment_id`, `scheduled_for`). Quando o agente legitimamente não consegue agendar, não há forma válida de reportar isso — a CLI sempre estoura Pydantic, mesmo que o modelo tenha entregado um envelope de erro bem-formado.

Afeta: o avaliador do desafio (roda exatamente o comando do README e vê exit 3 + stderr verboso, não a tabela ASCII). Afeta também qualquer operador que troque a fixture — hoje a pipeline só funciona com um único hash, e silenciosamente degrada para `[]`.

Por que importa agora: é o último bloqueio antes do E2E verde reprodutível. Sem output hardening, o trabalho feito em 0001–0008 + ADR-0009 não "aparece" na entrega.

## User stories

- Como **avaliador do desafio**, eu quero rodar `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` e ver a tabela ASCII com `appointment_id`, para que eu confirme o happy path sem precisar debugar container.
- Como **operador**, eu quero substituir a fixture por outra imagem e que o OCR reconheça deterministicamente, para que eu possa exercitar o sistema com pedidos médicos sintéticos distintos.
- Como **autor da CLI**, eu quero que o agente possa reportar "não consegui agendar" num envelope estruturado sem crashar o parser, para que o exit code diferencie `output malformado` de `agendamento falhou legitimamente`.
- Como **engenheiro de resiliência**, eu quero que um `LlmAgent` secundário reformate a saída bruta antes da validação Pydantic, para que pequenos drifts (fences, campos extras, texto prosa) não derrubem o run inteiro.

## Critérios de aceitação

- [AC1] Dado o PNG canônico em `/fixtures/sample_medical_order.png`, quando o agente chama `extract_exams_from_image`, então o tool devolve a lista de 5 exames de `_SAMPLE_EXAMS` **independente de como o modelo encodou o base64** (mesmo após round-trip via inline_data Gemini).
- [AC2] Dado que um teste registra uma fixture nova via `register_fixture(image_path, exams)`, quando qualquer caller passa o mesmo bytestream em base64, então `lookup()` devolve a lista registrada.
- [AC3] Dado que a resposta final do agente satisfaz `{"exams":[...], "appointment_id":..., "scheduled_for":...}`, quando a CLI parseia, então `_parse_runner_output` retorna `_RunnerOutput` com `status="success"` implícito e a CLI imprime a tabela ASCII (comportamento atual preservado).
- [AC4] Dado que a resposta final do agente satisfaz `{"error":{"code":str,"message":str,"hint":str|null}}`, quando a CLI parseia, então `_parse_runner_output` retorna um envelope de erro válido e a CLI sai com exit code `3` (E_AGENT_OUTPUT_REPORTED_ERROR distinto), imprimindo o envelope em stderr — **sem crashar Pydantic**.
- [AC5] Dado que a resposta final do agente não satisfaz nem a forma sucesso nem a forma erro, quando o validator-pass estiver **habilitado** (`AGENT_VALIDATOR_PASS_ENABLED=true`), então a CLI faz uma segunda chamada a `google.genai` com `response_json_schema` apontando para a união `success | error` e usa o resultado reformatado.
- [AC6] Dado que o validator-pass está **desabilitado** (default), quando a resposta é malformada, então o comportamento atual é preservado: exit 3 com `E_AGENT_OUTPUT_INVALID` e stderr descritivo.
- [AC7] Dado que o validator-pass falha (timeout, HTTP 5xx da API Gemini, JSON inválido na resposta do validator), quando a CLI processa, então **cai graciosamente** no parser atual — validator-pass nunca mascara bug do agente principal.
- [AC8] Dado o E2E real em `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` com `.env` default, quando o comando roda, então exit 0, stdout contém a tabela ASCII, e `docs/EVIDENCE/0009-output-hardening.md` captura o transcript.

## Robustez e guardrails

### Happy Path

`extract_exams_from_image(image_base64)` devolve 5 exames para a fixture canônica → modelo roda `search_exam_code` em paralelo → todos com `score ≥ 0.80` → `POST /api/v1/appointments` retorna `appointment_id` → modelo emite o JSON canônico → CLI valida contra `RunnerSuccess`, imprime tabela, exit 0.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| OCR devolve `[]` (hash desconhecido) | agente aborta com envelope `{error.code=E_OCR_UNKNOWN_IMAGE}` em vez de tentar `create_appointment` vazio | `E_OCR_UNKNOWN_IMAGE` | AC4 |
| Modelo emite JSON com fences ` ```json ` | `_strip_json_fence` remove (já existe); valida contra união | — | AC3, AC4 |
| Modelo emite prosa antes/depois do JSON | `_strip_json_fence` extrai primeiro `{...}` (já existe); valida | — | AC3, AC4 |
| Modelo emite schema de erro diferente (ex.: `{error_code,description}`) | validator-pass reformata se habilitado; senão exit 3 | `E_AGENT_OUTPUT_INVALID` | AC5, AC6 |
| Validator-pass excede `VALIDATOR_TIMEOUT_SECONDS` | fallback ao parser atual | `E_AGENT_OUTPUT_INVALID` (inalterado) | AC7 |
| Validator-pass devolve JSON que também não satisfaz união | fallback ao parser atual | `E_AGENT_OUTPUT_INVALID` (inalterado) | AC7 |
| Fixture PNG não existe no container | `_get_fixture_hash()` retorna `None` (já existe); OCR segue devolvendo `[]`; agente reporta `E_OCR_UNKNOWN_IMAGE` | `E_OCR_UNKNOWN_IMAGE` | AC4 |

### Guardrails

| Alvo | Cap / Timeout | Violação | AC ref |
|---|---|---|---|
| `VALIDATOR_TIMEOUT_SECONDS` (env) | default `15` s | fallback parser atual | AC7 |
| `VALIDATOR_MAX_INPUT_BYTES` (env) | default `16384` | validator-pass não é chamado; exit 3 | AC7 |
| `VALIDATOR_MODEL` (env) | default `gemini-2.5-flash-lite` (ADR-0009) | — | AC5 |

### Security & threats

- **Ameaça**: validator-pass recebe output não confiável do agente principal (pode conter prompt injection).
  **Mitigação**: prompt do validator é **puramente estrutural** ("reformate este texto para este JSON schema"); nenhuma tool é ligada; modelo nunca executa instruções do payload.
- **Ameaça**: validator-pass reformata um output que deveria ter sido rejeitado, mascarando bug silencioso no agente principal.
  **Mitigação**: (i) flag default desligada; (ii) log `agent.validator.applied` com `raw_hash`, `reformatted_hash`; (iii) teste E2E valida happy path sem validator-pass (AC3/AC8).

### Rastreabilidade DbC

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC1 | `extract_exams_from_image` | Post |
| AC2 | `fixtures.register_fixture` | Post |
| AC3 | `_parse_runner_output` (sucesso) | Post |
| AC4 | `_parse_runner_output` (erro) | Post |
| AC5 | `_run_validator_pass` | Post |
| AC7 | `_run_validator_pass` | Invariant |

## Requisitos não-funcionais

- **Desempenho**: validator-pass adiciona no máximo 1 round-trip Gemini (`< 5 s` p50, `< 15 s` p99). Não é chamado no happy path — só quando parser primário falha.
- **Observabilidade**: log estruturado `agent.validator.{start,applied,fallback,error}` com `correlation_id`, `raw_preview` (primeiros 200 chars, PII-masked).
- **Operabilidade**: flag única `AGENT_VALIDATOR_PASS_ENABLED=false` desliga feature inteira sem rebuild (ADR-0009 pattern).
- **Segurança**: validator-pass não recebe imagem original, só texto; prompt é hardcoded e auditável.

## Decisões (antes eram [NEEDS CLARIFICATION], resolvidas 2026-04-20)

- [x] **Q1 → evidence-first**: não assumir re-encode. Primeiro instrumentar o tool OCR com log `ocr.lookup.hash` (T041) + escrever T010 (lookup da fixture canônica). Rodar 1 E2E para observar o digest real que o Gemini envia. Se bater com o disco, a causa é outra (payload cortado, token limit, arg vazio) e o spec é revisitado antes de continuar. Se divergir, T042 registra o hash observado via `register_fixture`. **Nenhum fix no escuro.**
- [x] **Q2 → `google.genai` direto**: validator-pass chama `google.genai.Client.generate_content` sem ADK/Runner/tools. Usa `response_json_schema` nativo do SDK. Dispensa PII callback (texto já foi mascarado pelo agente principal).
- [x] **Q3 → exit code 4 novo**: `exit 3` = parser explodiu (bug no agente); `exit 4` = agente reportou impossibilidade legítima via `RunnerError` (ação do operador diferente). Addendum em ADR-0008 em T092.
- [x] **Q4 → herdar `correlation_id`**: validator-pass usa o mesmo `correlation_id` do run principal. Logs `agent.validator.*` permitem trace contínuo por `grep`.

## Fora de escopo

- Reescrita do prompt fixo do agente para evitar drift (mitigação óbvia mas ortogonal — o modelo sempre vai errar às vezes; o hardening é sobre absorver isso).
- Fixtures OCR por hash perceptual (pHash/dHash) — overkill pro MVP.
- Segundo agente com tools próprias (`orchestrator-worker`) — fora do padrão escolhido em ADR-0006.
- Testes de mutação do prompt para caracterizar taxa de drift do Gemini — vira projeto próprio.
- Mudança do modelo default (`gemini-2.5-flash-lite` → outro) — já é env via ADR-0009.
