---
id: 0011-real-ocr-tesseract
status: proposed
---

## Abordagem técnica

Substituir a estratégia "OCR = lookup determinístico por hash" por um **pipeline de OCR real** baseado em Tesseract, preservando a lookup de hash como **fast-path de cache** para a fixture canônica. Decisão arquitetural registrada em ADR-0011 (supersede parcial de R11). Reusa ADR-0001 (SSE), ADR-0003 (PII dupla camada — Layer 1 intacta), ADR-0008 (taxonomia de erro inalterada), ADR-0009 (nova env `OCR_TESSERACT_LANG`) e ADR-0010 (pré-OCR CLI consome a tool sem saber se veio do fast-path ou do Tesseract).

**Engine**: Tesseract 5 (Debian slim apt package `tesseract-ocr` + `tesseract-ocr-por`), wrapper `pytesseract>=0.3.10` + `Pillow>=10.0.0` para decoding de bytes → `PIL.Image`. Invocação: `pytesseract.image_to_string(img, lang="por")` — retorno multi-linha, splitado por `\n`, filtrado por heurísticas de cabeçalho e comprimento, cap de 64 linhas.

**Shape do código**:

```
ocr_mcp/
├── ocr_mcp/
│   ├── fixtures.py   # refactor: lookup() retorna list[str] | None (None = miss)
│   ├── ocr.py        # NOVO — extract_exam_lines(bytes, *, lang, timeout_s) -> list[str]
│   └── server.py     # _do_ocr orquestra: fixtures.lookup(b64) or ocr.extract_exam_lines(bytes)
└── Dockerfile        # apt-get install tesseract-ocr tesseract-ocr-por
```

## Data models

Nenhum modelo Pydantic novo. Apenas aliases internos em `ocr.py`:

```python
# ocr_mcp/ocr_mcp/ocr.py
from typing import TypeAlias

ExamLine: TypeAlias = str  # já pós-filtrada; não pós-PII-mask (server faz)

_HEADER_PREFIXES: frozenset[str] = frozenset({
    "paciente:", "data:", "cpf:", "médico:", "medico:",
    "crm:", "clínica:", "clinica:", "endereço:", "endereco:",
    "telefone:", "fone:",
})
_MIN_LINE_LEN: int = 3
_MAX_LINE_LEN: int = 120
_MAX_LINES: int = 64
```

## Contratos

### `ocr_mcp/ocr_mcp/ocr.py` (NOVO)

```python
async def extract_exam_lines(
    image_bytes: bytes,
    *,
    lang: str = "por",
    timeout_s: float = 5.0,
) -> list[str]:
    """Executa OCR real sobre image_bytes e retorna linhas candidatas a exame.

    Pre:
        image_bytes é um PNG/JPEG válido (Pillow consegue abrir).
        timeout_s > 0; lang ∈ pacotes instalados (ex: 'por').
        image_bytes tem tamanho ≤ OCR_IMAGE_MAX_BYTES (caller já validou).

    Post:
        Retorna list[str] com no máximo 64 itens, cada item com
        3 ≤ len ≤ 120, nenhum prefixado por cabeçalho conhecido.
        Retorna [] se zero linhas passam pelo filtro.
        NÃO aplica pii_mask (responsabilidade do caller — server._do_ocr).

    Raises:
        TesseractNotFoundError: binário ausente no sistema.
        TesseractError: falha interna do engine.
        PIL.UnidentifiedImageError: bytes não são imagem válida.
    """
```

### `ocr_mcp/ocr_mcp/fixtures.py::lookup` (SIGNATURE CHANGE)

```python
def lookup(image_base64: str) -> list[str] | None:
    """Fast-path por hash. Retorna None em miss (ANTES: []).

    Pre: image_base64 é base64 RFC 4648 válido.
    Post:
        - Hit: retorna cópia da lista canônica.
        - Miss: retorna None (sinaliza "delegar ao OCR real").
    """
```

**Breaking change interno** — único caller em produção é `server._do_ocr`. Test helpers que chamam `lookup` também mudam. `grep -r "fixtures.lookup\|from.*fixtures.*import.*lookup"` na Task T020 confirma antes do GREEN.

### `ocr_mcp/ocr_mcp/server.py::_do_ocr` (REFACTOR)

```python
async def _do_ocr(image_base64: str) -> list[str]:
    """Orquestra fast-path + OCR real + PII mask.

    Pre: image_base64 já validado (base64, tamanho ≤ 5 MB) pelo caller público.
    Post: retorno passou por pii_mask item-a-item.
    """
    from security import pii_mask
    from ocr_mcp import ocr

    names = fixtures.lookup(image_base64)
    if names is None:
        decoded = base64.b64decode(image_base64, validate=True)
        names = await ocr.extract_exam_lines(
            decoded, lang=_TESSERACT_LANG, timeout_s=_OCR_TIMEOUT_S
        )
    # PII masking Layer 1 (ADR-0003) — inalterado
    masked = []
    for n in names:
        r = await asyncio.to_thread(pii_mask, n, language=_DEFAULT_LANGUAGE)
        masked.append(r.masked_text)
    return masked
```

Envs novas:
- `OCR_TESSERACT_LANG` (default `"por"`) — lida no módulo server; passada a `ocr.extract_exam_lines`.

Contrato público da tool MCP `extract_exams_from_image(image_base64: str) -> list[str]` **não muda**. AC8 do spec garante.

## Design by Contract

| Alvo (função/classe/modelo) | Pre | Post | Invariant | AC ref | Task ref |
|---|---|---|---|---|---|
| `fixtures.lookup` | image_base64 é base64 válido | hit → lista canônica; miss → `None` | FIXTURES populado lazy | AC1, AC10 | T012 [DbC] |
| `ocr.extract_exam_lines` | image_bytes decodifica para Pillow; timeout_s > 0 | len(out) ≤ 64; cada item 3..120 chars; sem header prefix | filtro é idempotente | AC2, AC4 | T010, T011, T015 [DbC] |
| `server._do_ocr` | image_base64 já validado em guardrails | retorno pós-`pii_mask` (Layer 1) | delega a `ocr` só em miss | AC1, AC2, AC3 | T013, T014, T016 [DbC] |
| `server.extract_exams_from_image` | tool input não-nulo | exit via ToolError para E_*; list[str] em happy path | timeout hard 5 s | AC5, AC6 | T017 [DbC] |

**Onde declarar no código**:
- Docstrings Google-style com `Pre`, `Post`, `Invariant` (já convencionado no módulo `server.py`).
- `assert` em fronteiras de `ocr.extract_exam_lines` (stdlib) para garantir invariantes de saída (`assert all(3 <= len(x) <= 120 for x in result)`).

**Onde enforcar**:
- Cada linha desta tabela tem teste `[DbC]` em `tasks.md`.
- `code-reviewer` usa o trace triplo para aprovar.

## Dependências

Novas no `ocr_mcp/pyproject.toml` (`[project] dependencies`):

| Nome | Versão mínima | Motivo | Alternativa considerada |
|---|---|---|---|
| `pytesseract` | >=0.3.10,<1 | Wrapper Python para binário Tesseract; API estável desde 2022. | `tesserocr` (bindings C diretos — mais rápido mas mais frágil em Docker slim); rejeitado por custo de instalação. |
| `Pillow` | >=10.0.0,<12 | Decodifica bytes → PIL.Image para `pytesseract.image_to_string`. Já em dev-deps; promovido a runtime. | `opencv-python` (~40 MB extra); rejeitado — Pillow basta. |

Novas no `ocr_mcp/Dockerfile` (apt):

| Pacote | Motivo |
|---|---|
| `tesseract-ocr` | Binário core (~50 MB). |
| `tesseract-ocr-por` | Language pack português (~30 MB). |

## Riscos

| Ref | Risco | Mitigação |
|---|---|---|
| R1 | Tamanho da imagem `ocr-mcp` cresce ~100 MB, impactando build time e cold start. | Aceitável — ADR-0011 documenta explicitamente. `docker pull` fica em cache após primeiro build. |
| R2 | Tesseract retorna falsos positivos em imagens ruidosas (linhas de 1-2 chars, grafia errada). | Filtro `_MIN_LINE_LEN=3` + `_MAX_LINE_LEN=120` + header blacklist + cap de 64 linhas. Threshold 80 do rapidfuzz na RAG (ADR-0007) absorve erros pequenos. |
| R3 | `pytesseract.TesseractNotFoundError` em dev local onde avaliador não instalou binário. | Dockerfile garante binário no container; docs de desenvolvimento local explicam apt install. Falha é loud (`E_OCR_INTERNAL`), não silenciosa. |
| R4 | Signature change em `fixtures.lookup` (`[]` → `None`) pode quebrar callers esquecidos. | Task T020 faz `grep -r` antes de implementar; testes T012 garantem semântica nova; `mypy --strict` no CI pega miss. |
| R5 | OCR real sobre a fixture canônica extrai lista diferente da canônica do `_SAMPLE_EXAMS` (e.g., "Hemograma" em vez de "Hemograma Completo"). | Fast-path de hash **continua sendo o caminho preferido para a fixture**; hash hit antecede Tesseract. Se `.dockerignore` for corrigido em paralelo (fora de escopo desta spec — tarefa devops separada), fast-path cobre E2E da fixture canônica. Se não corrigido, Tesseract toma o caminho e retorno pode diferir da lista canônica; RAG absorve via fuzzy. |
| R6 | Cold start do container sobe 0.5–1 s por causa do Tesseract init. | Healthcheck `start_period: 15s` no Dockerfile (já existente) cobre; não é regressão operacional. |
| R7 | Escopo pode inflar em direção a "melhorar qualidade do OCR com preprocessing" (binarização, deskew, denoising). | Fora de escopo desta spec. Se necessário, abrir spec 0012 dedicada. Esta entrega mantém `image_to_string` default. |

## Estratégia de validação

### Testes unitários (em `ocr_mcp/tests/unit/`)

- `test_ocr.py::test_extract_returns_lines_from_synthesized_image` — PIL sintetiza uma imagem branca com `ImageDraw.text(..., "Hemograma Completo")` em fonte conhecida; Tesseract extrai "Hemograma Completo"; lista não-vazia.
- `test_ocr.py::test_extract_returns_empty_when_image_is_noise` — PIL gera `Image.new("RGB", (200, 100), "white")` sem texto; Tesseract retorna "" → filtro → `[]`.
- `test_ocr.py::test_filter_drops_header_prefixes` — input sintético "Paciente: João\nHemograma" → saída `["Hemograma"]`.
- `test_ocr.py::test_filter_caps_line_count_at_64` — 200 linhas válidas entram; só 64 saem.
- `test_fixtures.py::test_lookup_returns_none_on_miss` — hash desconhecido → `None` (não `[]`).
- `test_fixtures.py::test_lookup_returns_list_copy_on_hit` — hit retorna cópia; mutação do retorno não vaza para `FIXTURES`.
- `test_server.py::test_do_ocr_uses_fixture_fast_path` — mock `fixtures.lookup` retorna `["x"]`; `ocr.extract_exam_lines` é `AsyncMock` que assert-not-awaited.
- `test_server.py::test_do_ocr_falls_back_to_real_ocr_on_fixture_miss` — mock `fixtures.lookup` retorna `None`; `ocr.extract_exam_lines` é awaited com bytes decodificados corretos.
- `test_server.py::test_do_ocr_pii_masks_real_ocr_output` — `extract_exam_lines` retorna string com CPF cru; retorno da tool tem `<CPF>` (ou equivalente mascarado).

### Testes de integração (em `ocr_mcp/tests/integration/`, `@pytest.mark.integration`)

- `test_tesseract_available.py::test_binary_is_on_path` — `shutil.which("tesseract")` não é None; `subprocess.run(["tesseract", "--list-langs"], ...)` contém "por". **Só roda em container** (skip em local se binário ausente).
- `test_real_fixture_ocr.py::test_extract_from_canonical_fixture_png` — lê bytes de `ocr_mcp/tests/fixtures/sample_medical_order.png`; roda Tesseract real; asserta que ao menos uma linha contém substring "Hemograma" ou "Glicemia" (fuzzy, tolerante a imperfeições de Tesseract).

### Testes E2E (em `tests/e2e/`, reutilizando infraestrutura do bloco 0008)

- `test_e2e_real_ocr_happy.py::test_canonical_fixture_via_fast_path` — verifica que o E2E canônico continua exit `0` com a fixture (via fast-path de hash, assumindo `.dockerignore` corrigido em paralelo ou via fallback para OCR real que extrai linhas legíveis).

### Inspeção manual

- `docker build` local + `docker run ocr-mcp which tesseract` + `tesseract --list-langs | grep por`. Evidência capturada em `docs/EVIDENCE/0011-real-ocr-tesseract.md`.
- Build local + E2E manual com imagem **arbitrária** (não a fixture) — prova que o OCR real funciona, não apenas o fast-path.

## Notas operacionais

- O `.dockerignore` raiz exclui `tests/`. Consequência: a fixture PNG não entra no container. **Não corrigir o `.dockerignore` nesta spec** — ele é uma decisão de slim image independente. O fast-path de hash **deixa de cobrir o E2E Docker da fixture canônica até essa correção ser feita**, mas o OCR real cobre o mesmo caminho. Se o avaliador rodar com a fixture, Tesseract toma o volante; se o avaliador rodar com sua própria imagem, idem. Ambos funcionam.
- Se quisermos fast-path em Docker no futuro, abrir spec dedicada para (a) montar `./ocr_mcp/tests/fixtures` como volume read-only no compose, **ou** (b) mover fixture para um diretório que não é ignorado (`ocr_mcp/ocr_mcp/_data/`), **ou** (c) popular `FIXTURES` em build-time via arquivo gerado. Fora de escopo agora.
