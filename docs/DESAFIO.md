# Desafio Técnico: Sênior de Inteligência Artificial

> Transcrição fiel do PDF `DESAFIO_SENIOR_IA.pdf` para facilitar a consulta durante o desenvolvimento.

Ficamos felizes em ter você participando do nosso processo seletivo. Preparamos este desafio prático para entender como você aborda a construção e orquestração de agentes usando o **Google ADK**, além de avaliar as suas práticas de engenharia de software.

Nosso objetivo é analisar as suas decisões de arquitetura, a forma como garante a qualidade e segurança da solução e, principalmente, como utiliza a IA de forma consciente na geração de código — priorizando sempre a revisão e a validação em vez da cópia sem critério.

---

## O que você vai construir

A sua missão principal é criar um **transpilador**. Ele deve receber um **JSON** com a especificação de um agente e transformar esse input em **código Python** válido que, ao ser executado, instancie agentes utilizando exclusivamente o **Google ADK**.

O transpilador precisa ser robusto: deve validar os inputs, retornar mensagens de erro claras e garantir que o código gerado seja executável e siga as boas práticas do ecossistema.

---

## O Caso de Uso (Fictício)

Para dar contexto ao seu transpilador, considere o seguinte cenário numa clínica laboratorial: precisamos de um assistente de linha de comando (CLI) focado no agendamento de exames.

O fluxo que o agente (gerado pelo seu transpilador) deve seguir é:

1. **Entrada:** O sistema recebe a imagem de um pedido médico (fotografia, scan ou documento digitalizado). Notas manuscritas são bem-vindas para demonstrar a robustez do fluxo, mas não são obrigatórias.
2. **Extração (OCR via MCP):** O agente utiliza uma ferramenta de OCR, integrada via *Model Context Protocol (MCP)* com conexão **SSE**, para processar a imagem e extrair o **nome dos exames**.
3. **Consulta (RAG via MCP):** Com os nomes extraídos, o agente pesquisa os detalhes (como os códigos correspondentes) desses exames numa base de dados através de RAG (também integrada via MCP com SSE). Essa base pode ser uma implementação simulada (mock), mas deve conter **pelo menos 100 exames diferentes** (com nomes e respectivos códigos) para dar volume à pesquisa.
4. **Agendamento:** O agente submete os exames para uma API fictícia de agendamentos, que deve ser construída em **FastAPI**.
5. **Saída:** Por fim, o agente exibe no terminal a lista dos exames (com os respectivos códigos recuperados na base) e confirma a solicitação do agendamento junto à API.

> **Lembrete:** Todos os dados envolvidos devem ser fictícios. Não utilize dados reais ou sensíveis.

---

## Requisitos Técnicos

Para que a solução esteja alinhada ao perfil, é necessário cumprir os seguintes requisitos:

- **Integração MCP (SSE):** As ferramentas de OCR e RAG devem ser servidores MCP que se comunicam exclusivamente via *Server-Sent Events (SSE)*. Documente o processo para iniciar esses servidores e como o agente se conecta a eles.
- **API FastAPI:** A API de agendamento deve ser bem estruturada e ter os seus endpoints documentados de forma clara no Swagger (`/docs`), refletindo exatamente o contrato consumido pelo agente.
- **Camada de Segurança (PII):** Implemente uma etapa de qualidade e segurança no sistema capaz de detectar e anonimizar/mascarar dados sensíveis (nomes, documentos, contatos) extraídos da imagem **antes** que estes sejam enviados para um LLM ou persistidos.
- **Conteinerização:** Toda a solução (servidores MCP, API FastAPI e eventuais bancos de dados) deve ser conteinerizada utilizando exclusivamente **Docker**. A orquestração dos serviços deve ser feita através de um ficheiro `docker-compose.yml`.

---

## Critérios de Avaliação

Durante a nossa análise, iremos focar em:

- **Transpilador e Especificação:** O design do JSON é coerente? O código Python gerado pelo transpilador é eficiente e segue as boas práticas do ADK?
- **Fluxo End-to-End:** Validaremos a imagem de exemplo fornecida. O agente consegue processar a imagem, realizar a extração, consultar os dados via RAG e interagir com a API de agendamento com sucesso?
- **Engenharia e Infraestrutura:** Analisaremos a organização do repositório, a clareza dos commits, a cobertura de testes e a eficiência da conteinerização via Docker.
- **Arquitetura e Segurança:** A separação de responsabilidades (transpilador, runtime, MCPs, API e guardrails) é clara e está devidamente documentada?

---

## O que deve ser entregue

A submissão do desafio deve conter no seu repositório:

1. O **código-fonte** completo da solução (transpilador, servidores MCP, API FastAPI e configurações Docker).
2. Um **JSON de especificação** de exemplo.
3. Uma **imagem de teste** representando o pedido médico fictício.
4. Um **README** detalhado com instruções claras sobre como iniciar o ambiente Docker, rodar o transpilador e executar o agente final.
5. **Evidências de funcionamento** (logs da execução, capturas de tela da CLI, URL e interface do Swagger, etc.).

> **Observação:** Os itens listados e os requisitos técnicos representam o escopo mínimo esperado para a solução. Sinta-se totalmente livre para ir além e melhorar a robustez do processo (adicionar mais camadas de testes, melhorar o fluxo arquitetural, etc.), desde que se mantenha fiel ao contexto principal solicitado.

---

## Transparência e Uso de IA

Incentivamos o uso de ferramentas de IA para apoiar o desenvolvimento. Contudo, é essencial que isso seja feito de forma consciente, assegurando a revisão e o teste de todo o código gerado.

Para manter a transparência, adicione uma breve secção no seu README abordando:

- A abordagem adotada no desenvolvimento (ex: uso de IA como assistente de programação, iterações manuais, etc.).
- As principais referências e materiais consultados (ex: documentação oficial do ADK, guias MCP, tutoriais).
- A estratégia de orquestração implementada para o agente (fluxo sequencial, delegação a subagentes, processamento paralelo, etc.).

Essa documentação nos ajudará a compreender melhor as suas escolhas técnicas e o seu processo de engenharia.

Desejamos sucesso no desafio e aguardamos para analisar a sua solução técnica!
