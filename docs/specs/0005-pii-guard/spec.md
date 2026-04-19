---
id: 0005-pii-guard
title: Camada PII com Presidio + custom recognizers brasileiros
status: implemented
linked_requirements: [R05]
owner_agent: software-architect
created: 2026-04-18
---

## Problema

O desafio exige que PII (nomes, CPF/CNPJ, RG, telefones, e-mails) seja **anonimizada antes** de qualquer chamada a LLM e antes de persistir em qualquer lugar. O Presidio cobre as entidades globais mas **não oferece recognizers brasileiros nativos** (ver nota de correção de ADR-0003) — precisamos escrever os BR à mão. A camada é **dupla** (ADR-0003): linha 1 dentro do `ocr-mcp`, linha 2 no `before_model_callback` do agente.

- O que falta hoje? Módulo `security/` com função pública `pii_mask(text, language="pt") -> MaskedResult`, quatro custom recognizers BR (`BR_CPF`, `BR_CNPJ`, `BR_RG`, `BR_PHONE`) com validação quando aplicável, e suíte de testes.
- Quem é afetado? `ocr-mcp` (Bloco 3 importa), `generated_agent` (Bloco 6 usa no callback), `code-reviewer` (reprova commit que emita texto OCR sem pipeline de mask).
- Por que importa agora? É um gate **não-negociável** do desafio; falha aqui compromete a entrega inteira.

## User stories

- Como **ocr-mcp**, quero chamar `pii_mask(text)` antes de devolver a tool e obter `masked_text` sem valores brutos detectáveis.
- Como **agente ADK**, quero registrar um `before_model_callback` que reanalisa o prompt e bloqueia PII residual — **segunda linha de defesa**.
- Como **avaliador**, quero auditar que a lib realmente detecta CPF e nome em um texto médico PT-BR típico via relatório de cobertura de testes.
- Como **code-reviewer**, quero logs em que só aparece `(entity_type, start, end, score, sha256_prefix)` — nunca o valor cru.

## Critérios de aceitação

### API pública

- [AC1] Dado `from security import pii_mask`, quando chamado com `pii_mask("João Silva CPF 111.444.777-35", language="pt")`, então retorna `MaskedResult` onde `masked_text` contém placeholders `<PERSON>` e `<CPF>` e o texto cru original **não** aparece em `masked_text`.
- [AC2] Dado `pii_mask(text)` retorna `MaskedResult(masked_text, entities)`, quando `entities` é inspecionado, então cada item contém apenas `entity_type`, `start`, `end`, `score`, `sha256_prefix` — nenhum campo carrega o valor cru ([`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "PII Guard").
- [AC3] Dado um idioma não-suportado (ex.: `language="fr"`), quando `pii_mask` é chamado, então levanta `PIIError` com `code="E_PII_LANGUAGE"`.
- [AC4] Dado o motor Presidio não inicializa (ex.: modelo spaCy ausente), quando `pii_mask` é chamado, então levanta `PIIError` com `code="E_PII_ENGINE"` e hint sobre deps de `security/`.

### Custom recognizers BR

- [AC5] Dado `"CPF 111.444.777-35"`, quando detectado, então a entidade `BR_CPF` tem `score >= 0.85` (combinando regex + `pycpfcnpj.cpf.validate`) e o texto mascarado contém `<CPF>`.
- [AC6] Dado `"CPF 000.000.000-00"` (formato válido mas dígito inválido), quando analisado, então o `score` da entidade `BR_CPF` fica abaixo do threshold e o valor **não** é mascarado como CPF — evita falso-positivo.
- [AC7] Dado `"CNPJ 11.222.333/0001-81"`, quando detectado, então a entidade `BR_CNPJ` é reportada com `score >= 0.85` (regex + validação de dígitos).
- [AC8] Dado `"RG 12.345.678-9"`, quando detectado, então a entidade `BR_RG` é reportada via regex (sem validação de dígito — UFs variam).
- [AC9] Dado `"(11) 98765-4321"` ou `"11 987654321"`, quando detectado, então a entidade `BR_PHONE` é reportada via regex DDD + 9 dígitos.

### Entidades Presidio stock

- [AC10] Dado `"joao@exemplo.com"` no texto, quando `pii_mask` roda, então a entidade `EMAIL_ADDRESS` é detectada e o e-mail é mascarado como `<EMAIL>`.
- [AC11] Dado um texto com `"01/05/2026"` (data clínica), quando `pii_mask` roda, então a entidade `DATE_TIME` é detectada mas **não** mascarada (policy congelada em [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) § "Lista definitiva de entidades PII").

### Allow-list

- [AC12] Dado `pii_mask("hemograma completo", allow_list=["hemograma"])`, quando roda, então o token `hemograma` **não** é mascarado mesmo se Presidio o detectasse como entidade.

### Não-funcionais / cobertura

- [AC13] Cobertura de testes em `security/` ≥ 80 % (ADR-0004) com cada recognizer BR cobrindo pelo menos um caso positivo + um caso negativo explícito.
- [AC14] `pii_mask` é **idempotente** sob a propriedade: `pii_mask(pii_mask(text, language=lang).masked_text, language=lang).masked_text == pii_mask(text, language=lang).masked_text`. Aplicar a máscara duas vezes não altera o resultado — garante estabilidade da dupla camada (ADR-0003: linha 1 no OCR + linha 2 no `before_model_callback` não devem compor destrutivamente).
- [AC15] Dado `pii_mask(text, ...)` chamado com `text` > 100 KB, quando executado, então levanta `PIIError(code="E_PII_TEXT_SIZE")` citando bytes observados vs cap conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md); não invoca o Presidio.
- [AC16] Dado `pii_mask(text, allow_list=[...])` com `allow_list` > 1000 itens, quando executado, então levanta `PIIError(code="E_PII_ALLOW_LIST_SIZE")` citando cap, conforme [ADR-0008 § Guardrails](../../adr/0008-robust-validation-policy.md).
- [AC17] Dado que `pii_mask` excede 5 segundos de processamento, quando executado, então levanta `PIIError(code="E_PII_TIMEOUT")` conforme [ADR-0008 § Timeouts](../../adr/0008-robust-validation-policy.md).
- [AC18] Dado qualquer log emitido por qualquer função do módulo `security/`, quando inspecionado, então **nenhum campo** contém valor PII cru — apenas `entity_type`, `sha256_prefix` (primeiros 8 chars) e contadores; reforço da regra "no-PII-in-logs" de [ADR-0008 § No-PII-in-logs](../../adr/0008-robust-validation-policy.md).

## Robustez e guardrails

### Happy Path

`pii_mask("João Silva CPF 111.444.777-35 tel (11) 98765-4321", language="pt")` → retorna em < 100 ms `MaskedResult(masked_text="<PERSON> CPF <CPF> tel <PHONE>", entities=[...])`, nenhum valor cru em `masked_text` nem em logs.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| `text` > 100 KB | rejeitar antes de Presidio | `E_PII_TEXT_SIZE` | AC15 |
| `allow_list` > 1000 itens | rejeitar antes de Presidio | `E_PII_ALLOW_LIST_SIZE` | AC16 |
| Processamento > 5 s | timeout hard | `E_PII_TIMEOUT` | AC17 |
| `language` não-suportado | rejeitar na entrada | `E_PII_LANGUAGE` | AC3 |
| Presidio não inicializa | erro claro | `E_PII_ENGINE` | AC4 |
| Log com PII potencial | auditoria rejeita | — | AC18 |

### Guardrails

| Alvo | Cap | Violação | AC ref |
|---|---|---|---|
| `text` (bytes UTF-8) | 100 KB | `E_PII_TEXT_SIZE` | AC15 |
| `allow_list` | 1000 itens | `E_PII_ALLOW_LIST_SIZE` | AC16 |
| `pii_mask` (timeout) | 5 s | `E_PII_TIMEOUT` | AC17 |

### Security & threats

- **Ameaça**: cliente envia texto de 10 MB para mascarar e trava o motor Presidio.
  **Mitigação**: cap de 100 KB em bytes UTF-8 antes de invocar o motor (AC15). Motor não chega a ser chamado.
- **Ameaça**: `allow_list` com milhares de termos genéricos (`"a"`, `"o"`, ...) neutraliza a máscara.
  **Mitigação**: cap de 1000 itens conforme ADR-0008 (AC16).
- **Ameaça**: log vaza valor cru de CPF/nome detectado via `repr` ou f-string.
  **Mitigação**: `EntityHit` **nunca** carrega `value` (AC2); auditoria usa só `sha256_prefix` (AC18); teste `caplog` garante (T023).

### Rastreabilidade DbC

Mapa AC ↔ linha DbC do `plan.md § Design by Contract`.

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC1, AC2 | `pii_mask(text, language, allow_list)` | Post |
| AC2 | `MaskedResult.entities` | Invariant |
| AC5, AC6 | `BR_CPF` recognizer | Post |
| AC14 | `pii_mask(text, language, allow_list)` | Invariant (idempotência) |
| AC15, AC16 | `pii_mask(text, language, allow_list)` | Pre (caps ADR-0008) |
| AC17 | `pii_mask(text, language, allow_list)` | Post (timeout ADR-0008) |
| AC18 | `security/*` logging | Invariant (no-PII-in-logs ADR-0008) |

## Requisitos não-funcionais

- **Idempotência**: `pii_mask(pii_mask(x).masked_text).masked_text == pii_mask(x).masked_text` — aplicar a máscara duas vezes não muda o resultado (cria estabilidade na dupla camada).
- **Determinismo**: entidades e offsets são estáveis entre execuções para o mesmo input (snapshot-testable).
- **Sem PII em logs**: nenhum log do módulo contém valores crus; auditoria guarda apenas hash e tipo (GUIDELINES § 3).
- **Performance**: sub-100 ms para textos < 2 KB em dev local (Presidio PT-BR é rápido).
- **Type-check strict**: `mypy --strict` em `security/` (ADR-0005 / GUIDELINES).

## Clarifications

*(nenhuma — ADR-0003 e ARCHITECTURE congelam placeholders, entidades e política `DATE_TIME`.)*

## Fora de escopo

- Aplicação das máscaras (isso é responsabilidade dos blocos consumidores: 3 no OCR, 6 no callback).
- Mapeamento reversível (`<PERSON_1>` ↔ valor real). Explicitamente **rejeitado** em ADR-0003 — mascaramento é irreversível.
- Tradução multi-idioma além de `pt` e `en`.
- Detecção de dados médicos sensíveis (CID-10, medicamentos) — fora de PII stricto.
- Guardrails pós-LLM (ver `AGENTIC_PATTERNS § 2.6`).
