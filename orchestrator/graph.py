"""Router / Grafo - equivalente simplificado do Enterprise Router do
agent_platform_oci (LangGraph workflow).

Fluxo esperado (ver docs/ARQUITETURA.md, diagrama de sequencia):
Interaction -> guardrail de input -> agente (RAG + prompt + LLM) ->
guardrail de output -> resposta final. Cada etapa deve ser rastreada via
orchestrator/tracer.py.

TODO (AI Developer Sr): implementar o grafo LangGraph e run_interaction()
para satisfazer os testes de tests/test_integracao.py.

Pontos de atenção:
- Se o guardrail de input bloquear (Action.BLOCK), o fluxo deve pular
  direto para uma resposta de recusa, sem chamar o agente/LLM
- Se a consulta RAG não encontrar evidência (QueryResult.found=False), a
  resposta deve ser a padrão de "não encontrei" (agent.prompt.not_found_response()),
  sem chamar o LLM
- A resposta final deve passar pelo guardrail de output antes de retornar
- Cada interação deve ser envolvida por orchestrator.tracer.trace_interaction()
"""

from typing import TypedDict

from gateway.models import Interaction


class GraphState(TypedDict):
    conversation_id: str
    input_text: str
    guarded_input: str
    response: str
    blocked: bool


def build_graph():
    raise NotImplementedError


def run_interaction(interaction: Interaction) -> str:
    raise NotImplementedError
