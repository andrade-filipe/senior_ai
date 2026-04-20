---
id: 0011-real-ocr-tesseract
title: OCR real via Tesseract — substitui o mock como implementação principal
status: implemented
implemented: 2026-04-20
linked_requirements: [R02, R03, R06, R11]
owner_agent: software-architect
created: 2026-04-20
---

## Problema

Em 2026-04-20, durante o E2E canônico pós-spec 0010 (pré-OCR no CLI), o comando `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` saiu com exit `4` e envelope `E_OCR_UNKNOWN_IMAGE`. A investigação mostrou a causa: o dicionário `FIXTURES` de `ocr_mcp/ocr_mcp/fixtures.py` é populado por `_ensure_fixture_registered()`, que lê o PNG fixture em `ocr_mcp/tests/fixtures/sample_medical_order.png` e usa seu `sha256` como chave. No build de imagem Docker, porém, a raiz `.dockerignore` **exclui `tests/`** de todos os contextos — o arquivo simplesmente não viaja para dentro do container. Resultado: o dict permanece vazio em runtime, qualquer chamada `lookup()` devolve `[]`, e o CLI aborta com `E_OCR_UNKNOWN_IMAGE` mesmo para a fixture oficial do desafio.

O problema vai além do bug de `.dockerignore`. Ele expõe que a estratégia "OCR = lookup por hash" é frágil por construção: qualquer avaliador que salve o PNG com metadata EXIF distinta, recomprima, ou simplesmente use **outra imagem legível de pedido médico** recebe o mesmo erro. O enunciado do desafio é explícito — `DESAFIO.md` diz literalmente "a solução utiliza uma ferramenta de OCR" — e o R11 atual ("mock determinístico aceito no MVP") foi uma decisão de MVP nossa, não uma autorização do desafio. Com o pré-OCR agora no CLI (ADR-0010), o caminho de extração é determinístico em orquestração mas não em extração: a função que **realmente lê a imagem** ainda é um dict de hashes. Precisamos trocar essa função por um OCR real sem quebrar o contrato da tool MCP (`extract_exams_from_image(image_base64) -> list[str]`), preservar PII masking, e manter o fast-path de hash para testes determinísticos.

Afeta: o **avaliador do desafio**, que provavelmente submeterá seu próprio PNG e precisa ver a tabela ASCII; o **operador**, que quer trocar a fixture sem reaprender o sistema; o **engenheiro de QA**, que precisa de testes que cubram o caminho real (não apenas o fast-path); o **engenheiro DevOps**, que precisa do apt package `tesseract-ocr-por` no Dockerfile. Por que importa agora: é o último bloqueio para o E2E verde funcionar com **qualquer imagem legível**, não apenas com a fixture canônica (já quebrada em Docker por motivo independente — o fix do `.dockerignore` sozinho conserta a fixture mas não resolve o problema de fundo).

## User stories

- Como **avaliador do desafio**, eu quero subir qualquer PNG legível de pedido médico via `--image` e ver a tabela ASCII com `appointment_id`, para que eu teste o sistema com meus próprios exemplos, não só com a fixture do repo.
- Como **operador**, eu quero trocar a imagem de entrada sem precisar registrar um hash novo no código, para que eu exercite o fluxo com pedidos sintéticos distintos.
- Como **engenheiro de resiliência**, eu quero que o fast-path de hash continue funcionando para a fixture canônica (zero latência, determinístico em CI), para que a suíte rápida permaneça rápida.
- Como **mantenedor**, eu quero que o OCR real falhe honestamente (retorna lista vazia → `E_OCR_UNKNOWN_IMAGE`) quando não extrai nada legível, sem fallback silencioso, para que o log conte a história real.

## Critérios de aceitação

- [AC1] Dado uma imagem registrada no dict `FIXTURES` (hash conhecido), quando `extract_exams_from_image(image_base64)` roda, então retorna exatamente a lista canônica do fixture (fast-path), sem invocar Tesseract, e emite log `ocr.lookup.hit` (campo `event`).
- [AC2] Dado uma imagem **não registrada** mas legível (pedido médico com nomes de exame visíveis), quando a tool roda, então invoca `ocr.extract_exam_lines(image_bytes, lang=OCR_TESSERACT_LANG, timeout_s=OCR_TIMEOUT_SECONDS)`, retorna a lista de linhas filtradas, e emite dois logs: `ocr.tesseract.invoked{image_size, lang}` antes do parse e `ocr.tesseract.result{filtered_line_count, duration_ms, lang}` depois.
- [AC3] Dado o resultado do OCR real, quando a tool devolve, então cada string passou por `security.pii_mask()` (ADR-0003 Layer 1), preservando o comportamento atual. Nenhum CPF/nome/contato cru aparece no retorno.
- [AC4] Dado uma imagem ilegível (ruído, em branco, sem texto reconhecível), quando o Tesseract retorna zero linhas plausíveis após filtragem, então a tool retorna `[]` e o CLI aborta com envelope `E_OCR_UNKNOWN_IMAGE` (exit `4`). **Sem fallback silencioso**.
- [AC5] Dado uma imagem > `OCR_IMAGE_MAX_BYTES` (5 MB decoded), quando a tool roda, então aborta antes de chamar Tesseract com `E_OCR_IMAGE_TOO_LARGE` (comportamento preservado).
- [AC6] Dado Tesseract travando além de `OCR_TIMEOUT_SECONDS` (5 s), quando a tool roda, então `asyncio.wait_for` preempta e aborta com `E_OCR_TIMEOUT` (comportamento preservado — `pytesseract.image_to_string` roda em `asyncio.to_thread`).
- [AC7] Dado o Docker image de `ocr-mcp`, quando construído via `docker build`, então contém os pacotes apt `tesseract-ocr` e `tesseract-ocr-por`; `which tesseract` retorna `/usr/bin/tesseract`; `tesseract --list-langs` lista `por`.
- [AC8] Dado o contrato público da tool MCP, quando invocado pelo pré-OCR do CLI (spec 0010), então a assinatura permanece `extract_exams_from_image(image_base64: str) -> list[str]`; nenhum parâmetro novo; nenhum código de erro novo.
- [AC9] Dado o fixture canônico `sample_medical_order.png` do repo, quando o E2E `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` roda com `.env` default, então exit `0`, tabela ASCII presente, `appointment_id` presente. A evidência é capturada em `docs/EVIDENCE/0011-real-ocr-tesseract.md`.
- [AC10] Dado a função `fixtures.lookup(image_base64)`, quando o hash da imagem não está em `FIXTURES`, então retorna `None` (não `[]`) — sinalizando explicitamente "miss, delegar ao OCR real". Specs anteriores (0003) que tratavam `[]` como "unknown image" são compatíveis via contrato `server._do_ocr`, não mudam.

## Robustez e guardrails

### Happy Path

CLI chama `session.call_tool("extract_exams_from_image", {"image_base64": b64})` → server decoda, valida tamanho → chama `fixtures.lookup(b64)` → **miss** (`None`) → chama `ocr.extract_exam_lines(decoded_bytes, lang="por", timeout_s=5.0)` → Tesseract roda em thread, retorna texto multi-linha → filtro remove cabeçalhos (`"Paciente:"`, `"Data:"`, `"CPF:"`), linhas curtas (< 3 chars) e muito longas (> 120 chars) → lista resultante passa item-a-item por `pii_mask` → retorno ao CLI.

### Edge cases

| Situação | Tratamento | Código de erro | AC ref |
|---|---|---|---|
| Hash conhecido em `FIXTURES` | fast-path: retorna lista canônica sem invocar Tesseract | — (sucesso) | AC1 |
| Hash desconhecido, imagem legível | delega ao Tesseract, filtra, PII-mask, retorna | — (sucesso) | AC2 |
| Hash desconhecido, Tesseract retorna zero linhas plausíveis | retorna `[]` | `E_OCR_UNKNOWN_IMAGE` (exit 4, no CLI) | AC4 |
| Imagem > 5 MB | rejeita antes de decodificar Tesseract | `E_OCR_IMAGE_TOO_LARGE` | AC5 |
| Tesseract trava > 5 s | `asyncio.wait_for` preempta | `E_OCR_TIMEOUT` | AC6 |
| `pytesseract.TesseractNotFoundError` (binário ausente) | log `ocr.tesseract.missing{error}` + `ToolError[E_OCR_INTERNAL]` — **falha loud**, não mascara como unknown image | `E_OCR_INTERNAL` (já existe na taxonomia) | AC2 (complemento) |
| Imagem com texto em outro idioma (p.ex. inglês puro) | Tesseract roda mesmo assim (`lang="por"` é hint, não restrição hard); filtro de cabeçalho é PT-BR; resultado pode ser ruim mas não falha | — | P2 (sem AC hard-gate) |
| Imagem multi-página (PDF-like PNG concatenado) | fora de escopo; Tesseract processa como página única | — | out-of-scope |
| Imagem com caracteres não-latinos (CJK) | fora de escopo | — | out-of-scope |

### Guardrails

| Alvo | Cap / Timeout | Violação | AC ref |
|---|---|---|---|
| `image_base64` decoded | 5 MB (`OCR_IMAGE_MAX_BYTES`) | `E_OCR_IMAGE_TOO_LARGE` | AC5 |
| `extract_exams_from_image` total | 5 s (`OCR_TIMEOUT_SECONDS`) | `E_OCR_TIMEOUT` | AC6 |
| Linhas extraídas por imagem | 64 (constante no `ocr.py`; previne blow-up em imagem ruidosa com OCR "alucinando" milhares de linhas de 1-char) | truncamento silencioso com log `ocr.tesseract.truncated{raw_count}` | P2 (sem AC hard-gate) |
| Tamanho de linha filtrada | min 3 chars, max 120 chars | filtro descarta | parte de AC2 (heurística) |

### Security & threats

- **Ameaça**: imagem manipulada faz Tesseract consumir CPU/RAM indefinidamente.
  **Mitigação**: `asyncio.wait_for` com 5 s hard timeout (AC6) + cap de tamanho decoded (AC5).
- **Ameaça**: PII vaza via output do Tesseract (nome do paciente, CPF, etc.).
  **Mitigação**: `pii_mask` aplicado item-a-item antes do retorno (AC3). Idêntico ao caminho atual do fast-path.
- **Ameaça**: log estruturado vaza PII bruta do texto OCR.
  **Mitigação**: logs emitem apenas `image_size`, `duration_ms`, `filtered_line_count`, `lang`. **Nunca** o conteúdo textual. (O `sha256` do payload é emitido em log separado `ocr.lookup.hash` pela spec 0009 T041, antes de qualquer chamada ao Tesseract.)
- **Ameaça**: `tesseract-ocr-por` baixa modelo de fonte não confiável.
  **Mitigação**: instalado via `apt-get` padrão do Debian slim (repos oficiais); sem pip download arbitrário.

### Rastreabilidade DbC

| AC | DbC target (plan.md) | Tipo |
|---|---|---|
| AC1 | `fixtures.lookup` fast-path | Post |
| AC2 | `ocr.extract_exam_lines` | Post |
| AC3 | `server._do_ocr` | Post (Layer 1 PII) |
| AC4 | `ocr.extract_exam_lines` — retorno vazio honesto | Post |
| AC5 | `server.extract_exams_from_image` guard | Pre |
| AC6 | `server.extract_exams_from_image` timeout | Invariant |
| AC10 | `fixtures.lookup` miss semantics | Post |

## Requisitos não-funcionais

- **Latência**: OCR real sobre a fixture canônica (9469 bytes) deve completar em < 3 s no perfil CI/Docker (p95). Fast-path de hash deve completar em < 10 ms.
- **Tamanho de imagem Docker**: `ocr-mcp` cresce ~100 MB (binário Tesseract + language data `por`). Aceitável — outros serviços permanecem slim.
- **Cobertura**: ocr.py deve ter ≥ 85 % de cobertura unitária.
- **Compatibilidade**: zero breaking changes no contrato MCP público. Pré-OCR do CLI (spec 0010) não muda.

## [NEEDS CLARIFICATION]

- [ ] **Filtro de cabeçalho**: a lista inicial de prefixos a descartar é `["Paciente:", "Data:", "CPF:", "Médico:", "CRM:", "Clínica:", "Endereço:", "Telefone:"]`. OK ou há outros comuns em pedidos reais? **Default proposto no plan**: a lista acima + case-insensitive match.
- [ ] **Heurística de comprimento**: aceitar linhas entre 3 e 120 caracteres. OK? **Default proposto no plan**: sim, esses limites.
- [ ] **Suporte ao `OCR_TESSERACT_LANG` env**: proposta adicionar env com default `"por"`. Confirma? **Default proposto no plan**: sim; consistente com ADR-0009 (config via env).

## Fora de escopo

- GPU / aceleração de hardware.
- OCR multi-página (PDF, imagem concatenada).
- Idiomas além do português brasileiro.
- Reconhecimento de manuscrito.
- Correção ortográfica automática pós-OCR (o threshold 80 do rapidfuzz na RAG já absorve imperfeições de pequenos erros de caractere).
- Troca do engine por alternativas (EasyOCR, PaddleOCR, Google Vision) — documentada como rejeitada no ADR-0011.
