---
id: 0008-e2e-evidence-transparency
status: proposed
---

## Abordagem técnica

Três entregáveis independentes, orquestrados em sequência final. Reforço end-to-end da política de [ADR-0008](../../adr/0008-robust-validation-policy.md): auditoria de logs contra padrões PII + validação do shape canônico de erro em cenários de falha induzidos.

1. **Teste E2E (política dupla)**:
   - **CI leve (automatizado)**: GitHub Actions roda `docker compose up -d` + aguarda healthchecks + executa suítes unit + integration dos serviços (marker `@pytest.mark.e2e_ci`). **Não** chama Gemini real — evita custo, rate limit e risco de leak de secret.
   - **E2E completo (manual)**: fluxo com chamada Gemini real, executado localmente pelo avaliador/desenvolvedor. Documentado no README com passo-a-passo reprodutível; evidência capturada em `docs/EVIDENCE/0008-e2e-evidence-transparency.md` com logs + print da tabela final.
2. **Evidências por bloco**: cada bloco produz `docs/EVIDENCE/NNNN-<slug>.md` no seu próprio passo 7 (evidence) do ciclo SDD+TDD — **um arquivo por bloco**, **sem agregador único**. O `README.md` final lista todos por link. Template fixo (abaixo).
3. **README final** em `README.md` (raiz) em PT-BR, cobrindo quickstart, arquitetura, stack, estrutura de diretórios, **seção "Transparência e Uso de IA"** (R12) e o passo-a-passo do E2E manual.

### Teste E2E

```python
# tests/e2e/test_full_flow.py
@pytest.mark.e2e
def test_agent_e2e_flow(tmp_path):
    subprocess.run(["docker", "compose", "up", "-d", "ocr-mcp", "rag-mcp", "scheduling-api"], check=True)
    try:
        wait_for_healthy("http://localhost:8000/health", timeout=60)
        proc = subprocess.run([
            "docker", "compose", "run", "--rm", "generated-agent",
            "--image", "/fixtures/sample_medical_order.png",
        ], capture_output=True, check=True)
        # AC1: exit code 0 (check=True covers)
        # AC2: verify appointment in API
        resp = httpx.get("http://localhost:8000/api/v1/appointments").raise_for_status()
        assert resp.json()["total"] >= 1
        # AC3: patient_ref masked
        for appt in resp.json()["items"]:
            assert re.match(r"^anon-[a-z0-9]+$", appt["patient_ref"])
    finally:
        subprocess.run(["docker", "compose", "down", "-v"], check=False)
```

Helper `wait_for_healthy` faz polling em `/health` com timeout.

### Evidências

Cada arquivo de evidência segue template fixo:

```markdown
# Evidência — Bloco NNNN-<slug>

## Comandos reproduzíveis
```
(bash)
```

## Log trimado
```
(linhas essenciais, correlation_id destacado)
```

## Cobertura
```
coverage report snippet
```

## Screenshots
(embedded ou linked; Bloco 4 tem swagger-ui.png; Bloco 6 tem cli-output.png)
```

### README

Estrutura proposta (detalhe fica em RED/GREEN):

```markdown
# Desafio Técnico Sênior IA — Transpilador ADK + MCP-SSE + FastAPI + PII Guard

[badge CI]

## Visão geral
(diagrama mermaid — referência ou inline)

## Stack
(uv, Gemini 2.5 flash, ADK, MCP-SSE, FastAPI, Presidio, Docker)

## Quickstart
```bash
cp .env.example .env  # preencher GOOGLE_API_KEY
docker compose up -d
docker compose run --rm generated-agent --image /fixtures/sample_medical_order.png
```

## Arquitetura
Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Estrutura do repositório
(lista 1-liner: docs/, ai-context/, transpiler/, security/, ocr_mcp/, rag_mcp/, scheduling_api/, generated_agent/)

## Evidências
Por bloco em [docs/EVIDENCE/](docs/EVIDENCE/).

## Transparência e Uso de IA
- Como foi desenvolvido (Claude Code + 8 subagentes — mapa em `.claude/agents/`).
- Fluxo SDD+TDD formalizado em [ADR-0004](docs/adr/0004-sdd-tdd-workflow.md); artefatos em [docs/specs/](docs/specs/).
- Referências consultadas em [ai-context/LINKS.md](ai-context/LINKS.md).
- Auditoria de design em [ai-context/references/DESIGN_AUDIT.md](ai-context/references/DESIGN_AUDIT.md).
- Patterns agentic aplicados em [ai-context/references/AGENTIC_PATTERNS.md](ai-context/references/AGENTIC_PATTERNS.md).

## Licença
(a definir pelo autor)
```

## Data models

Nenhum modelo de dado novo. Consome dados de todos os outros blocos.

## Contratos

Não introduz contratos. Consome todos os contratos dos Blocos 3, 4, 6 via E2E.

## Design by Contract

**Não aplicável — invariantes herdadas dos blocos 1–7.** Este bloco é a camada de orquestração/fechamento: os critérios de aceitação (AC1..AC15) do `spec.md` são as invariantes E2E que o sistema composto deve honrar, mas não introduzem pré/pós/invariantes próprios de função/classe que exijam tabela DbC local.

- AC2 (appointment criado na API), AC3 (`patient_ref` sempre mascarado), AC1a/AC1b (exit code 0), AC14 (no-PII-in-logs ponta-a-ponta), AC15 (shape canônico de erro validado em cada componente) são invariantes de sistema fim-a-fim derivadas das tabelas DbC dos plans 0001..0007 e de ADR-0008.
- DbC por função já está declarado nos plans dos blocos 1–7 com colunas `AC ref` / `Task ref` — aqui só orquestramos e validamos externamente via E2E (`@pytest.mark.e2e_ci` + E2E manual).

Referência obrigatória: tabelas DbC dos plans dos blocos 1–7 devem ter testes `[DbC]` verdes antes deste bloco começar o E2E completo. `spec.md § Rastreabilidade DbC` deste bloco confirma a não-aplicabilidade.

**Estratégia de validação atualizada (ADR-0008)**:
- **No-PII-in-logs ponta-a-ponta (AC14)**: `scripts/audit_logs_pii.py` lê `docker compose logs` coletado após teardown e varre cada linha contra regex PII de ARCHITECTURE (CPF, CNPJ, RG, telefone BR, e-mail); exit ≠ 0 se houver match. Job CI falha explicitamente.
- **Shape canônico de erro (AC15)**: `tests/e2e/test_error_shape.py` induz erros em cada componente (transpiler com spec inválido, OCR com base64 > 5 MB, RAG com query vazia, API com body > 256 KB) e valida que stderr/body serializam `{code, message, hint, path, context}`.

## Dependências

| Nome | Versão mínima | Motivo |
|---|---|---|
| `pytest` | `^8` | Framework E2E |
| `httpx` | `^0.27` | Assertions HTTP no E2E |
| `docker` + `docker compose` | como Bloco 7 | Runtime do E2E |

Nenhuma dep runtime para a aplicação.

## Riscos

| Risco | Mitigação |
|---|---|
| E2E é flaky (race condition entre `up -d` e API pronta). | `wait_for_healthy` com polling + timeout configurável; fallback para dormir 2 s antes de polling. |
| CI não tem orçamento/segredo para chamar Gemini no E2E completo. | Divisão dupla já fixada: CI roda apenas E2E leve (compose up + healthchecks + unit/integration sem Gemini); E2E completo é manual, documentado no README e capturado em evidência. |
| Screenshots da Swagger/CLI podem ficar desatualizados se API evolui. | Regenerar como parte do checkpoint #2 do bloco correspondente (4 para Swagger, 6 para CLI). |
| README inchado viola GUIDELINES § 6 (linkar em vez de duplicar). | Cap de 500 linhas auto-imposto; revisão humana no checkpoint #2. |
| Transparência omite subagente ou referência crítica. | Cross-check com `.claude/agents/` (lista de 8) e `ai-context/LINKS.md` (lista completa) antes de finalizar. |

## Estratégia de validação

- **Same-commit** (ADR-0004): testes E2E + código da CLI helper juntos.
- **E2E**: uma execução local + uma execução CI (se viável — ver clarification) por PR que toca infra. Para PRs de escopo pequeno, E2E pode ser skip-default (marcador `@pytest.mark.e2e`).
- **README** validado por inspeção humana no checkpoint #2 coletivo: cobre 11 ACs (AC9–AC11).
- **Evidências** validadas via script simples `scripts/check_evidence.py` que assere existência de `docs/EVIDENCE/<block>.md` para cada pasta em `docs/specs/` (fica opcional; baixa prioridade).
- **Fixtures** (AC7, AC8): `test_fixtures.py` assere `sample_medical_order.png` existe + `spec.example.json` valida via Bloco 1.
- **Status final** (AC12, AC13): checklist manual no checkpoint #2 coletivo final.

## Dependências entre blocos

- **Depende, em código**, de **todos** os blocos anteriores estarem em GREEN — é o bloco de fechamento.
- Em termos de **spec/contrato**: **independente** — pode ser escrito em paralelo com os outros na fase de spec (já é o caso aqui, checkpoint #1 coletivo).
- **Fecha** o desafio: ao terminar, todos os `spec.md` ficam `implemented`, `STATUS.md` mostra todos `done`.
