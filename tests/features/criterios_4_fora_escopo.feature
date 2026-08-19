Feature: §4 — Perguntas fora do catálogo não geram resposta inventada
  Critério de aceite §4 do docs/CRITERIOS-DE-ACEITE.md:
  quando o usuário pergunta sobre um plano que não consta no catálogo,
  o agente informa explicitamente que não encontrou a informação,
  sem alucinar ou inventar dados sobre o plano inexistente.

  Estratégia de teste: perguntas contêm palavras-chave do catálogo
  (ex: "plano", "gigas") para que o roteador envie ao catalog_agent,
  mas o plano em questão não existe — o RAG retorna found=False e
  o grafo usa not_found_response() sem chamar o LLM.

  @unit @criterio_4
  Scenario: Plano inexistente no catálogo não gera resposta inventada
    Given uma mensagem "Quais gigas inclui o Plano Diamante Exclusivo da TIM?"
    When o agente processa com LLM mockado retornando "qualquer resposta mockada"
    Then a resposta indica que a informação não foi encontrada

  @unit @criterio_4
  Scenario: Pacote inexistente no catálogo não gera resposta inventada
    Given uma mensagem "Quero contratar o Plano Invisível Ultra 200GB"
    When o agente processa com LLM mockado retornando "qualquer resposta mockada"
    Then a resposta indica que a informação não foi encontrada

  @live_llm @criterio_4 @integration
  Scenario: Plano inexistente com LLM real não gera alucinação
    Given uma mensagem "Quais gigas inclui o Plano Diamante Exclusivo da TIM?"
    When o agente processa via Flow CI&T
    Then a resposta indica que a informação não foi encontrada
