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


def build_prompt(question: str, query_result: QueryResult) -> str | None:
    raise NotImplementedError


def not_found_response() -> str:
    raise NotImplementedError
