# Requisitos — Desafio Sênior IA

Enumeração estável dos requisitos extraídos de [`DESAFIO.md`](./DESAFIO.md). Cada requisito tem um **ID imutável** (R01..Rn) que specs e tasks vão citar no frontmatter para auditar rastreabilidade.

> Regra: esta lista só muda em uma situação — se o desafio for reinterpretado. Nesse caso, abre-se ADR nova e o requisito afetado é marcado como `superseded`. IDs **não são reaproveitados**.

## Tabela

| ID | Requisito | Origem em DESAFIO.md | Notas |
|---|---|---|---|
| R01 | **Transpilador JSON → Python ADK**: recebe um JSON com especificação de um agente e produz código Python executável usando exclusivamente o Google ADK. Valida inputs, retorna erros claros, gera código determinístico e executável. | "O que você vai construir" + "Requisitos Técnicos" | Schema fechado (ver ADR-0006). |
| R02 | **Servidor MCP de OCR via SSE**: extrai o nome dos exames de uma imagem de pedido médico. | "O Caso de Uso" passo 2 + "Requisitos Técnicos" § Integração MCP (SSE) | Mock determinístico aceito no MVP (ver R10). |
| R03 | **Servidor MCP de RAG via SSE com ≥ 100 exames**: dado um nome de exame, retorna código e metadados. Catálogo mock aceito. | "O Caso de Uso" passo 3 + "Requisitos Técnicos" § Integração MCP (SSE) | Busca via rapidfuzz (ADR-0007). |
| R04 | **API FastAPI de agendamento com Swagger**: endpoints bem estruturados, documentados em `/docs`, contrato idêntico ao consumido pelo agente. | "O Caso de Uso" passo 4 + "Requisitos Técnicos" § API FastAPI | Contrato em `docs/ARCHITECTURE.md`. |
| R05 | **Camada de segurança PII**: detecta e anonimiza nomes, documentos, contatos extraídos da imagem **antes** de qualquer chamada a LLM ou persistência. | "Requisitos Técnicos" § Camada de Segurança (PII) | Dupla camada (ADR-0003). |
| R06 | **Agente ADK end-to-end**: consome OCR → RAG → API de agendamento e exibe no terminal a lista de exames com códigos + confirmação do agendamento. | "O Caso de Uso" passo 5 | Topologia LlmAgent único (ADR-0006). |
| R07 | **Containerização completa via Docker + `docker-compose.yml`**: todos os serviços (MCPs, API, agente) sobem com um único comando. | "Requisitos Técnicos" § Conteinerização | Stack em ADR-0005. |
| R08 | **Evidências de funcionamento**: logs de execução, capturas de tela da CLI, interface do Swagger. | "O que deve ser entregue" § 5 | Por marco em `docs/EVIDENCE/`. |
| R09 | **README principal em português** com quickstart, instruções de Docker, explicação da arquitetura e seção "Transparência e Uso de IA". | "O que deve ser entregue" § 4 + "Transparência e Uso de IA" | Última fase (entrega). |
| R10 | **Imagem de teste e JSON de especificação de exemplo** no repositório. | "O que deve ser entregue" §§ 2 e 3 | Fixture (`sample_medical_order.png` + `spec.example.json`). |
| R11 | **Mock de OCR determinístico aceito no MVP**: dado um hash de imagem, retorna texto canônico; permite OCR real ser plugado no futuro sem quebrar contrato. | Decisão interna (projeto não exige OCR real) | Justificado em ADR posterior se trocarmos para OCR real. |
| R12 | **Transparência no uso de IA**: seção no README com abordagem de desenvolvimento, referências consultadas e estratégia de orquestração. | "Transparência e Uso de IA" | `ai-context/LINKS.md` alimenta esta seção. |

## Critérios de avaliação (do desafio) → requisitos

Os critérios em DESAFIO.md § "Critérios de Avaliação" mapeiam assim:

| Critério | Requisitos atingidos |
|---|---|
| Transpilador e Especificação | R01 |
| Fluxo End-to-End | R02, R03, R04, R06, R10 |
| Engenharia e Infraestrutura | R07, R08, R09 + qualidade (cobertura, testes, docs) |
| Arquitetura e Segurança | R05 + separação de responsabilidades documentada em `docs/ARCHITECTURE.md` |

## Como usar no ciclo SDD

Cada `docs/specs/NNNN-<slug>/spec.md` carrega no frontmatter um campo `linked_requirements: [Rxx, Ryy]`. O `code-reviewer` reprova spec cujos requisitos linkados não sejam atendíveis pelos critérios de aceitação listados.
