Feature: §3 — Perguntas respondidas com fonte RAG
  Critério de aceite §3 do docs/CRITERIOS-DE-ACEITE.md:
  o agente responde perguntas sobre planos com base em documentos do catálogo,
  sem inventar informações fora do corpo de evidência retornado pelo RAG.

  O papel de AI Developer Sr (Igor Scaglia) garante que o grafo LangGraph
  propaga o QueryResult (contrato de Ana — rag_pipeline/query_api.py) até
  o LLM call e devolve a resposta ao canal.

  @unit @criterio_3
  Scenario: Franquia do Turbo 40GB respondida sem LLM externo
    Given uma mensagem "Quais franquias de dados o Plano Turbo 40GB inclui?"
    When o agente processa com LLM mockado retornando "O Plano Turbo 40GB inclui 40 GB de internet de alta velocidade."
    Then a resposta contém "40"
    And o traço contém chunk_id "turbo-40gb"

  @live_llm @criterio_3 @integration
  Scenario: Franquia do Turbo 40GB respondida pelo Flow CI&T
    Given uma mensagem "Quais franquias de dados o Plano Turbo 40GB inclui?"
    When o agente processa via Flow CI&T
    Then a resposta contém "40"

  @unit @criterio_3
  Scenario: Fidelidade do Família Prime respondida sem LLM externo
    Given uma mensagem "Existe período de fidelidade no Plano Família Prime?"
    When o agente processa com LLM mockado retornando "Sim, o Plano Família Prime exige 24 meses de fidelidade."
    Then a resposta contém "24"
    And o traço contém chunk_id "familia-prime"

  @live_llm @criterio_3 @integration
  Scenario: Fidelidade do Família Prime respondida pelo Flow CI&T
    Given uma mensagem "Existe período de fidelidade no Plano Família Prime?"
    When o agente processa via Flow CI&T
    Then a resposta contém "24"

  @unit @criterio_3
  Scenario: Multa do Controle 20GB respondida sem LLM externo
    Given uma mensagem "Qual o valor da multa de cancelamento do Plano Controle 20GB?"
    When o agente processa com LLM mockado retornando "A multa de cancelamento do Plano Controle 20GB é de R$ 240,00."
    Then a resposta contém "240"
    And o traço contém chunk_id "controle-20gb"

  @live_llm @criterio_3 @integration
  Scenario: Multa do Controle 20GB respondida pelo Flow CI&T
    Given uma mensagem "Qual o valor da multa de cancelamento do Plano Controle 20GB?"
    When o agente processa via Flow CI&T
    Then a resposta contém "240"
