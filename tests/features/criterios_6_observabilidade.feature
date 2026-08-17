Feature: §6 — Traço de observabilidade legível e rastreável
  Critério de aceite §6 do docs/CRITERIOS-DE-ACEITE.md:
  cada interação emite um traço legível contendo: latência total, chunk_id do
  documento RAG utilizado, e lista de guardrails acionados com suas violações.

  Duas camadas de observabilidade (ver orchestrator/tracer.py):
    1. AgentObserver (agent_framework — SPEC-007-lite): noop local, real em OCI
    2. Log estruturado local (expansão do AI Dev Sr): TRACE|type|key=value

  O sumário final é emitido por log_sumario_interacao() ao fim de run_interaction().

  @unit @criterio_6
  Scenario: Traço de latência e session_id registrados após interação RAG
    Given uma mensagem "Quais franquias o Plano Turbo 40GB inclui?"
    When o agente processa com LLM mockado retornando "O Turbo 40GB inclui 40 GB de internet."
    Then o traço SUMARIO contém "latencia_ms"
    And o traço SUMARIO contém "session_id"

  @unit @criterio_6
  Scenario: Traço de chunk_id registrado para consulta RAG bem-sucedida
    Given uma mensagem "Quais franquias o Plano Turbo 40GB inclui?"
    When o agente processa com LLM mockado retornando "O Turbo 40GB inclui 40 GB de internet."
    Then o traço contém chunk_id "turbo-40gb"

  @unit @criterio_6
  Scenario: Traço de guardrail registrado para mensagem com PII
    Given uma mensagem "Meu CPF é 111.222.333-44. Quero saber sobre planos."
    When o agente processa com LLM mockado retornando "Temos ótimos planos para você."
    Then o traço SUMARIO contém "guardrails_acionados"

  @unit @criterio_6
  Scenario: Traço indica chunk_id nenhum para perguntas fora do catálogo
    Given uma mensagem "Quanto custa o iPhone 15 Pro?"
    When o agente processa com LLM mockado retornando "Não posso responder sobre isso."
    Then o traço SUMARIO contém "chunk_id=nenhum"
