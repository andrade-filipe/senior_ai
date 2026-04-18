# ADR-0003: PII mascarada em dupla camada (OCR + `before_model_callback`)

- **Status**: accepted
- **Data**: 2026-04-18
- **Autor(es)**: software-architect (decisão) + Filipe Andrade (aprovação)

## Contexto

`docs/DESAFIO.md` seção "Camada de Segurança (PII)" exige que dados pessoais sensíveis sejam **anonimizados antes** de qualquer chamada a LLM e antes de persistência. O desafio não prescreve onde aplicar a máscara, mas deixa claro que o escape de PII compromete a entrega.

Temos duas fronteiras naturais onde PII pode escapar:
1. **Saída do OCR** — o texto extraído de uma imagem de pedido médico pode conter nome, CPF, telefone, endereço do paciente.
2. **Prompt do LLM** — qualquer string que chegue ao modelo (instrução, histórico de mensagens, resposta de tools) pode conter PII.

Uma camada única em um desses pontos cobre o caminho feliz, mas falha se um bug ou caminho alternativo bypassa ela.

## Alternativas consideradas

1. **Camada única no OCR MCP** — mascara na fonte; depois, o texto sanitizado atravessa o pipeline sem mais checagens.
   - Prós: baixa latência, responsabilidade centralizada.
   - Contras: se o agente buscar PII em outra tool (ex.: RAG que retorna metadados) ou se for injetada manualmente na instruction, ela vaza.

2. **Camada única no `before_model_callback`** — última barreira antes do LLM.
   - Prós: cobre qualquer origem.
   - Contras: depende de o callback estar sempre presente; se o desenvolvedor gerar um agente sem callback (ou pular a cadeia), PII vaza. Também não protege persistência (ex.: logs do OCR MCP que capturem input raw).

3. **Dupla camada (escolhida)** — OCR mascara ao retornar + callback mascara antes do LLM. Defesa em profundidade.
   - Prós: falha única em qualquer camada ainda é mitigada pela outra; auditável; testável isoladamente.
   - Contras: custo de CPU dobrado no pior caso (texto já anonimizado passa por Presidio de novo). Mitigação: o Presidio é rápido em PT-BR e o texto de um pedido médico é curto (centenas de caracteres).

## Decisão

Aplicar `security.pii_mask()` em **duas** posições não-negociáveis:

1. **Dentro do `ocr-mcp`**, imediatamente antes de retornar o resultado da tool `extract_exams_from_image`.
2. **No agente ADK**, via `before_model_callback` registrado no `LlmAgent`, que reanaliza e anonimiza qualquer prompt antes de enviar ao Gemini.

O módulo `security/` expõe uma única função pública `pii_mask(text, language="pt") -> MaskedResult` usada nas duas camadas. Logs nunca contêm o texto bruto — apenas `(entity_type, sha256_prefix, score)` em auditoria.

## Consequências

- **Positivas**: PII não vaza mesmo se uma das camadas for bypassada; auditoria testável; alinhado à exigência do desafio.
- **Negativas**: 2× CPU de Presidio no caminho OCR→agente; custo aceitável dado o tamanho dos textos envolvidos.
- **Impacto**: `security-engineer` garante a função determinística; `adk-mcp-engineer` registra o callback no template do `generated_agent`; `code-reviewer` reprova commit que emita texto via OCR sem passar pelo mask.

### Trade-off: mascaramento irreversível

Chip Huyen (*AI Engineering*, cap. 5) descreve uma alternativa: substituir PII por placeholders **reversíveis** (mapping `{"<PERSON_1>": "João da Silva"}` guardado fora do prompt), de modo que a resposta final do agente possa ser des-anonimizada para o usuário. Essa abordagem preserva personalização, mas **exige** que o mapping viva em algum storage — o que contradiz a exigência do `docs/DESAFIO.md` de não persistir PII. Decisão: o mascaramento é **irreversível**; o agente nunca "re-humaniza" a saída. Consequência prática: a tabela final mostrada ao usuário contém `<PERSON>`, `<CPF>` etc. Se o avaliador pedir saída humanizada, isso vira ADR nova.

### Risco operacional: stream completion

Huyen (*cap. 6* — guardrails) alerta que PII guards aplicados só ao prompt **não** cobrem a resposta do LLM. O Gemini pode gerar PII por alucinação (ex.: inventar um CPF plausível no texto de confirmação). Em modo streaming, tokens saem antes de o guard pós-resposta ter chance de inspecionar. Mitigação adotada: o template do `generated_agent` desativa streaming (`run_live=False` / equivalente ADK) no MVP; qualquer retorno do LLM passa íntegro pelo `after_model_callback` (opcional, Bloco 6) antes de chegar ao usuário. Adoção plena de guardrails de saída está no backlog — ver `ai-context/references/AGENTIC_PATTERNS.md § 2`.

## Referências

- `docs/DESAFIO.md` — seção "Camada de Segurança (PII)"
- `ai-context/references/PII.md`
- https://microsoft.github.io/presidio/
- https://microsoft.github.io/presidio/supported_entities/
- https://adk.dev/callbacks/ — `before_model_callback`
- https://github.com/matheuscas/pycpfcnpj — validação de dígitos CPF/CNPJ (lib BR consolidada)

> Corrigido em 2026-04-18 durante auditoria pré-implementação: Presidio **não fornece** recognizers brasileiros nativos (`BR_CPF`, `BR_CNPJ`, `BR_RG`, `BR_PHONE` não existem na lib, confirmado em `https://microsoft.github.io/presidio/supported_entities/` — países cobertos: US, UK, Spain, Italy, Poland, Singapore, Australia, India, Finland, Korea, Nigeria, Thailand; Brasil ausente). Os quatro reconhecedores BR serão escritos pelo `security-engineer` como custom recognizers, cada um combinando regex + validação de dígitos via `pycpfcnpj` (onde aplicável). Impacto no esforço: Bloco 5 ganha ~0.5 pessoa-dia de codificação extra + testes unitários dos recognizers. O `before_model_callback` (ADR-0003 decisão central) foi confirmado como existente e capaz de mutar `llm_request.contents[].parts[].text` (ver `https://adk.dev/callbacks/`).
