# ADR-0011: OCR real via Tesseract (fast-path de hash preservado como cache)

- **Status**: accepted
- **Data**: 2026-04-20
- **Autor(es)**: software-architect (proposta) + Filipe Andrade (aprovação — checkpoint #1 em 2026-04-20)

## Contexto

Em 2026-04-20, após o fechamento do checkpoint #1 da spec 0010 (pré-OCR no CLI), o E2E canônico `docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png` saiu com exit `4` e envelope `E_OCR_UNKNOWN_IMAGE`. Investigação apontou **dois problemas sobrepostos**:

1. **Bug de `.dockerignore`**: o arquivo raiz exclui `tests/` de todos os contextos de build. A fixture `ocr_mcp/tests/fixtures/sample_medical_order.png` **não entra no container**, e `fixtures._ensure_fixture_registered()` encontra o arquivo ausente, deixa `FIXTURES` vazio, e todo `lookup()` devolve `[]`. A instrumentação `ocr.lookup.hash` (spec 0009 T041) expôs o hash correto chegando ao server — o miss é do dict, não do pipeline pré-OCR.
2. **Problema arquitetural de fundo**: mesmo com o `.dockerignore` corrigido, a estratégia "OCR = lookup por hash SHA-256" é frágil por construção. Qualquer avaliador que salve o mesmo PNG com metadata EXIF diferente, recomprima, ou simplesmente use outra imagem legível de pedido médico recebe `E_OCR_UNKNOWN_IMAGE`. O **enunciado do desafio** é explícito: `DESAFIO.md` diz "a solução utiliza uma ferramenta de OCR". O R11 em `docs/REQUIREMENTS.md` ("mock determinístico aceito no MVP") foi uma decisão interna de redução de escopo, não autorização do desafio.

Spec 0010 (pré-OCR invocado pelo CLI) resolveu o determinismo de **orquestração** do passo 1 (a CLI chama a tool em vez de depender da LLM reencaminhar bytes). Mas a função que realmente **lê a imagem** continua sendo um dict de hashes. Falta determinismo de **extração**.

Fontes:
- `DESAFIO.md` (fonte da verdade) — texto do passo 2: "A ferramenta de OCR processa a imagem e retorna o nome dos exames".
- Incidente 2026-04-20 (E2E canônico pós-0010) — evidência anexada em `docs/EVIDENCE/0010-pre-ocr-invocation.md § Follow-up incident`.
- R11 em `docs/REQUIREMENTS.md` — "mock determinístico aceito no MVP".
- ADR-0010 — estabeleceu pré-OCR no CLI; este ADR complementa no plano de extração.
- ADR-0003 — PII dupla camada, Layer 1 intacta.
- ADR-0009 — config via env (nova env `OCR_TESSERACT_LANG`).

## Alternativas consideradas

1. **Tesseract 5 via `pytesseract` (escolhida)** — binário instalado via apt no Dockerfile, wrapper Python invoca `image_to_string`, filtro heurístico limpa saída.
   - Prós: offline (sem API keys), estável (Tesseract 5 tem ~2 décadas de maturidade), language pack `por` mantido pelo Google, imagem Docker cresce apenas ~100 MB, zero custo operacional.
   - Contras: qualidade inferior a modelos cloud (Vision, Textract) em documentos ruidosos; requer apt package extra no Dockerfile.
2. **Google Cloud Vision OCR** — API gerenciada com qualidade top.
   - Prós: qualidade excelente; sem peso na imagem.
   - Contras: (a) **exige API key** — entrega do desafio não pressupõe credenciais externas além da Gemini; (b) violaria o princípio offline-friendly do repo; (c) latência de rede indeterminística em CI; (d) custo por chamada. Rejeitada.
3. **EasyOCR / PaddleOCR (modelos neurais locais)** — bibliotecas Python com modelos pré-treinados.
   - Prós: qualidade superior em imagens ruidosas; suporte multi-idioma nativo.
   - Contras: (a) imagem Docker cresce 1–3 GB (PyTorch runtime + modelos); (b) cold start de 2–5 s (download de modelos no primeiro uso); (c) overkill para o escopo do desafio; (d) violaria guardrail de imagem slim documentado implicitamente em ADR-0005. Rejeitada.
4. **Manter apenas fixture dict + consertar `.dockerignore`** — solução mínima para o bug imediato.
   - Prós: zero trabalho além do patch de `.dockerignore` + `volumes:` no compose.
   - Contras: (a) avaliador que usar outra imagem ainda quebra; (b) enunciado do desafio exige OCR; (c) viola o princípio "falhar honestamente" — o sistema ficaria limitado ao hash da fixture. Rejeitada pelo usuário como "não-profissional para uma entrega sênior".
5. **OCR local com LLM visual (Gemini vision multimodal)** — usar o próprio Gemini para OCR.
   - Prós: reaproveita credencial existente; qualidade alta.
   - Contras: (a) custo por chamada escala com uso; (b) volta exatamente ao problema que ADR-0010 resolveu (bytes binários para o modelo); (c) latência e dependência de rede no hot path; (d) não-determinístico. Rejeitada.

## Decisão

**Adotar Alternativa 1 (Tesseract 5 via pytesseract)** com arquitetura híbrida:

- **Fast-path de hash**: `fixtures.lookup(image_base64)` continua existindo, com a **signature change** `list[str] | None` (`None` em miss). Serve como cache determinístico para testes unitários rápidos e para a fixture canônica em ambiente onde o PNG está acessível.
- **Fallback real**: em miss do fast-path, `server._do_ocr` chama `ocr.extract_exam_lines(decoded_bytes, lang=OCR_TESSERACT_LANG, timeout_s=OCR_TIMEOUT_SECONDS)`. Este é o **caminho principal em produção** (Docker, com PNGs arbitrários do avaliador).
- **PII masking intacto**: `pii_mask` (ADR-0003 Layer 1) aplica-se item-a-item em ambos os caminhos, após a lista canônica ou após o OCR real. Nenhuma mudança no contrato de saída.
- **Contrato público inalterado**: tool MCP `extract_exams_from_image(image_base64: str) -> list[str]` permanece idêntica. Pré-OCR do CLI (spec 0010) não muda.
- **Dependências novas**: `pytesseract>=0.3.10`, `Pillow>=10.0.0` em runtime; apt `tesseract-ocr` + `tesseract-ocr-por` no Dockerfile.
- **Nova env**: `OCR_TESSERACT_LANG` (default `"por"`) na ADR-0009.
- **Sem novos códigos de erro**: taxonomia ADR-0008 suficiente. `E_OCR_UNKNOWN_IMAGE` (exit 4) agora se torna **semanticamente honesto** — dispara quando o OCR real genuinamente extrai zero linhas plausíveis, não quando um dict falha em ter um hash.

**Supersede parcial de R11**: R11 autorizava "mock determinístico aceito no MVP". Após este ADR, R11 é **parcialmente superseded** — mock continua autorizado apenas como **fast-path cache** (camada de performance/determinismo para testes), não como implementação principal. `docs/REQUIREMENTS.md` ganha nota de supersedência.

## Consequências

### Positivas

- **Entrega robusta para o avaliador**: qualquer PNG legível funciona; sistema deixa de ser acoplado a um hash específico.
- **Semântica honesta do `E_OCR_UNKNOWN_IMAGE`**: o código dispara quando OCR de verdade falha, não quando um dict de lookup não tem uma chave.
- **Fast-path preserva velocidade de testes**: a fixture canônica (quando acessível) continua resolvendo em ~1 ms; suite unitária não fica mais lenta.
- **Aderência textual ao enunciado do desafio**: "a solução utiliza uma ferramenta de OCR" deixa de ser interpretação benevolente.
- **Alinhamento com ADR-0010**: pré-OCR no CLI continua sendo o passo determinístico de orquestração; agora a extração também é real.
- **RAG absorve imperfeições**: threshold 80 do rapidfuzz (ADR-0007) cobre pequenos erros de OCR ("Hemograma Completa" vs "Hemograma Completo").

### Negativas / débito técnico

- **Imagem `ocr-mcp` cresce ~100 MB** (binário Tesseract + language data `por`). Aceitável; não viola nenhum guardrail explícito.
- **Cold start** do container sobe ~0.5–1 s por causa do Tesseract init. Healthcheck `start_period: 15s` já cobre.
- **Qualidade do OCR depende da qualidade da imagem**. Em imagens blurry, a lista vem ruim; o filtro heurístico pode não salvar. Mitigação: RAG fuzzy + log `ocr.tesseract.invoked{duration_ms, exam_count}` dá visibilidade.
- **Signature change em `fixtures.lookup`** (`[]` → `None`) é breaking. Único caller em produção é `server._do_ocr`; testes T020 grep-first + `mypy --strict` no CI pegam esquecimentos.
- **Fixture no container**: o bug de `.dockerignore` permanece como problema independente. Esta ADR **não corrige** o `.dockerignore` — a solução de fundo é o OCR real, que funciona com ou sem fixture no container. Se quisermos restaurar o fast-path da fixture em Docker, abrir spec separada.

### Impacto em outros subsistemas

- `ocr_mcp/ocr_mcp/`: módulo novo `ocr.py`; refactor menor em `fixtures.py` e `server.py`.
- `ocr_mcp/pyproject.toml`: 2 deps novas (runtime).
- `ocr_mcp/Dockerfile`: 1 bloco apt-get novo; imagem cresce ~100 MB.
- `docker-compose.yml`: nova env `OCR_TESSERACT_LANG=${OCR_TESSERACT_LANG:-por}` no service `ocr-mcp`.
- `.env.example`: nova entrada.
- `docs/REQUIREMENTS.md`: nota em R11 registrando supersedência parcial.
- `docs/adr/README.md`: entrada nova (ADR-0011) + anotação em R11 referenciada.
- **Sem mudança**: `generated_agent/`, `transpiler/`, `scheduling_api/`, `rag_mcp/`, `security/`. ADR-0010, ADR-0003, ADR-0008 permanecem integralmente válidos.

## Supersede

- **R11** em `docs/REQUIREMENTS.md`: mock de OCR determinístico autorizado apenas como fast-path cache; implementação principal passa a ser Tesseract real. Registrar em `docs/REQUIREMENTS.md` com link para este ADR.

## Referências

- `docs/specs/0011-real-ocr-tesseract/spec.md`, `plan.md`, `tasks.md`.
- `docs/EVIDENCE/0010-pre-ocr-invocation.md` — evidência do incidente 2026-04-20 que originou esta spec.
- ADR-0001 (transporte MCP via SSE) — inalterado.
- ADR-0003 (PII dupla camada) — Layer 1 preservada no pipeline novo.
- ADR-0008 (taxonomia de erro) — `E_OCR_*` códigos reutilizados sem adição.
- ADR-0009 (config via env) — nova env `OCR_TESSERACT_LANG`.
- ADR-0010 (pré-OCR no CLI) — este ADR é o complemento de extração.
- R11 em `docs/REQUIREMENTS.md` — superseded parcialmente.
- https://github.com/tesseract-ocr/tesseract — binário.
- https://pypi.org/project/pytesseract/ — wrapper Python.
- https://packages.debian.org/bookworm/tesseract-ocr-por — language pack.
