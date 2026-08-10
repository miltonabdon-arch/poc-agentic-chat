"""Prompt do agente - injeta QueryResult como contexto.

Regra central: sem evidencia (found=False), nunca inventar - responder
explicitamente que a informacao nao foi encontrada. Mesma filosofia de
'sem evidencia, sem invencao' de pipeline-rag-base/design.md.

TODO (AI Scientist / LLM Specialist): implementar build_prompt() e
not_found_response() para satisfazer os testes de tests/test_agent.py.

Contrato:
- build_prompt() retorna None se query_result.found for False (o
  orquestrador deve usar not_found_response() nesse caso, sem chamar o LLM)
- build_prompt() retorna um prompt que inclui o texto do chunk
  (query_result.text) e a fonte (query_result.source_document_id), e
  instrui o modelo a sempre citar a fonte
"""

from rag_pipeline.models import QueryResult

_NOT_FOUND_MSG = (
    "Não encontrei essa informação no catálogo de planos e ofertas disponível. "
    "Por favor, consulte um atendente ou acesse o site oficial da TIM para mais detalhes."
)


def build_prompt(question: str, query_result: QueryResult) -> str | None:
    if not query_result.found:
        return None
    return (
        "Você é um assistente de voz especializado em planos e ofertas da TIM. "
        "Responda APENAS com base na evidência abaixo. "
        "Escreva em prosa fluida, como se estivesse falando — sem listas, sem marcadores, "
        "sem markdown, sem colchetes ou símbolos especiais. "
        "Refira-se ao plano pelo nome natural presente na evidência, nunca pelo ID técnico.\n\n"
        f"[CONTEXTO INTERNO — não mencionar na resposta] fonte: {query_result.source_document_id}\n"
        f"Evidência: {query_result.text}\n\n"
        f"Pergunta do cliente: {question}"
    )


def not_found_response() -> str:
    return _NOT_FOUND_MSG
