"""Router / Grafo - equivalente simplificado do Enterprise Router do
agent_platform_oci (LangGraph workflow).

Fluxo (ver docs/ARQUITETURA.md, diagrama de sequencia):
Interaction -> guardrail de input -> agente (RAG + prompt + LLM) ->
guardrail de output -> resposta final. Cada etapa e rastreada via
orchestrator/tracer.py.

Pontos de atenção:
- Se o guardrail de input bloquear (Action.BLOCK), o fluxo pula direto
  para a resposta de recusa, sem chamar o agente/LLM
- Se a consulta RAG não encontrar evidência (QueryResult.found=False), a
  resposta é a padrão de "não encontrei" (agent.prompt.not_found_response()),
  sem chamar o LLM
- A resposta final passa pelo guardrail de output antes de retornar
- rag_pipeline.query_api.query() e rag_pipeline.vectorizer.get_client()
  são responsabilidade do Data Engineer (ver PAPEIS-E-ENTREGAVEIS.md) -
  este módulo assume que já estarão implementados no Checkpoint 1
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from agent.guardrails.input_guardrail import check_input
from agent.guardrails.output_guardrail import check_output
from agent.llm_client import complete
from agent.models import Action
from agent.prompt import build_prompt, not_found_response
from gateway.models import Interaction
from orchestrator.tracer import trace_interaction
from rag_pipeline.query_api import query
from rag_pipeline.vectorizer import get_client


class GraphState(TypedDict):
    conversation_id: str
    input_text: str
    guarded_input: str
    response: str
    blocked: bool


def _node_input_guardrail(state: GraphState) -> GraphState:
    result = check_input(state["input_text"])
    state["guarded_input"] = result.text
    state["blocked"] = result.action_taken == Action.BLOCK
    if state["blocked"]:
        state["response"] = result.text
    return state


def _node_agent(state: GraphState) -> GraphState:
    if state["blocked"]:
        return state

    client = get_client()
    query_result = query(client, state["guarded_input"])
    prompt = build_prompt(state["guarded_input"], query_result)
    if prompt is None:
        state["response"] = not_found_response()
        return state

    state["response"] = complete(prompt)
    return state


def _node_output_guardrail(state: GraphState) -> GraphState:
    if state["blocked"]:
        return state

    result = check_output(state["response"])
    state["response"] = result.text
    return state


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("input_guardrail", _node_input_guardrail)
    graph.add_node("agent", _node_agent)
    graph.add_node("output_guardrail", _node_output_guardrail)

    graph.set_entry_point("input_guardrail")
    graph.add_edge("input_guardrail", "agent")
    graph.add_edge("agent", "output_guardrail")
    graph.add_edge("output_guardrail", END)

    return graph.compile()


def run_interaction(interaction: Interaction) -> str:
    with trace_interaction(interaction.session_id) as record:
        graph = build_graph()
        result = graph.invoke(
            {
                "conversation_id": interaction.session_id,
                "input_text": interaction.text,
                "guarded_input": "",
                "response": "",
                "blocked": False,
            }
        )
        record("interaction.completed", blocked=result["blocked"])
        return result["response"]
