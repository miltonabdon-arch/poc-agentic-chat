"""Orquestrador LangGraph — AI Developer Sr (Igor Scaglia).

Responsabilidade: montar o grafo que une as fatias dos colegas usando
os contratos definidos em ARQUITETURA.md como cola entre as partes.

  Ana Carolina  → QueryResult      (rag_pipeline/query_api.py)
  Gustavo       → GuardrailResult  (agent/guardrails/, branch test_new_branch)
  Kirllen       → ChannelMessage   (gateway/channel_gateway.py, branch backend)
  Igor (este arquivo) → build_graph(), run_interaction(), _run_catalog(), etc.

Fluxo do grafo (PAPEIS-E-ENTREGAVEIS.md — AI Developer Sr):
  input_guardrails → routing_decision → [catalog|billing|cancellation|
  deals|eligibility|simulation|supervisor] → output_guardrails → judge → END

Expansão sobre o framework:
  O agent_platform_oci fornece EnterpriseRouter e ChannelMessage, mas NÃO
  monta o StateGraph — essa topologia (nós, arestas, condicionais) é
  responsabilidade explícita do AI Developer Sr (ver PAPEIS-E-ENTREGAVEIS.md).
"""

from __future__ import annotations

import logging
import os
import time
from types import SimpleNamespace
from typing import Any

import httpx
from agent_framework.channels.base import ChannelMessage
from agent_framework.routing.enterprise_router import EnterpriseRouter
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from orchestrator.tracer import log_sumario_interacao, trace_interaction

logger = logging.getLogger(__name__)

MOCK_BASE = os.environ.get("MOCK_SERVICES_URL", "http://localhost:8001")
MOCK_CPF = "12345678900"

_router_settings = SimpleNamespace(
    ROUTING_CONFIG_PATH="orchestrator/routing_config.yaml",
    ENABLE_LLM_ROUTER=False,
)
_router = EnterpriseRouter(_router_settings)


# ---------------------------------------------------------------------------
# Estado do grafo
# ---------------------------------------------------------------------------

class GraphState(TypedDict):
    channel_message: ChannelMessage
    sanitized_input: str       # saída do input_guardrail (PII mascarado ou texto original)
    route: str                 # agente escolhido pelo EnterpriseRouter
    intent: str
    answer: str
    final_answer: str
    blocked: bool
    guardrail_decisions: list[Any]
    # chunk_id: adicionado pelo AI Dev Sr para propagar o identificador do
    # documento RAG até o sumário de observabilidade (CRITERIOS-DE-ACEITE §6).
    # O agent_framework não carrega esse campo — é extensão local da PoC.
    chunk_id: str | None


# ---------------------------------------------------------------------------
# Nós do grafo — Passe 1 (esqueleto)
# ---------------------------------------------------------------------------

async def node_input_guardrails(state: GraphState) -> GraphState:
    from agent.guardrails.input_guardrail import check_input
    from agent.models import Action

    result = check_input(state["channel_message"].text)
    blocked = result.action_taken == Action.BLOCK
    await trace_interaction(
        "GRL",
        state["channel_message"],
        {"guardrail": "input", "violation": result.violation.value, "blocked": blocked},
    )
    return {
        **state,
        "sanitized_input": result.text,
        "blocked": blocked,
        "guardrail_decisions": [result],
    }


async def node_routing_decision(state: GraphState) -> GraphState:
    decision = await _router.route({"sanitized_input": state["sanitized_input"]})
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "routing_decision", "intent": decision.intent, "agent": decision.agent},
    )
    return {**state, "route": decision.agent, "intent": decision.intent}


async def node_catalog_agent(state: GraphState) -> GraphState:
    # _run_catalog retorna (resposta, chunk_id) para que o chunk_id
    # chegue ao sumário de observabilidade — ver CRITERIOS-DE-ACEITE §6.
    answer, chunk_id = await _run_catalog(state["sanitized_input"], state["channel_message"])
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "catalog_agent", "chunk_id": chunk_id},
    )
    return {**state, "answer": answer, "chunk_id": chunk_id}


async def node_billing(state: GraphState) -> GraphState:
    answer = await _run_billing(state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "billing"})
    return {**state, "answer": answer}


async def node_handoff_cancellation(state: GraphState) -> GraphState:
    answer = await _handoff("cancellation", state["sanitized_input"], state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "handoff_cancellation"})
    return {**state, "answer": answer}


async def node_handoff_deals(state: GraphState) -> GraphState:
    answer = await _handoff("deals", state["sanitized_input"], state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "handoff_deals"})
    return {**state, "answer": answer}


async def node_eligibility(state: GraphState) -> GraphState:
    answer = await _run_eligibility(state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "eligibility"})
    return {**state, "answer": answer}


async def node_simulation(state: GraphState) -> GraphState:
    answer = await _run_simulation(state["sanitized_input"], state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "simulation"})
    return {**state, "answer": answer}


async def node_supervisor(state: GraphState) -> GraphState:
    await trace_interaction("NOC", state["channel_message"], {"node": "supervisor"})
    return {
        **state,
        "answer": (
            "Olá! Sou o assistente TIM. Posso ajudar com planos, fatura, "
            "cancelamento ou negociação. Como posso te ajudar?"
        ),
    }


async def node_output_guardrails(state: GraphState) -> GraphState:
    from agent.guardrails.output_guardrail import check_output

    result = check_output(state["answer"])
    await trace_interaction(
        "GRL",
        state["channel_message"],
        {"guardrail": "output", "violation": result.violation.value},
    )
    decisions = list(state.get("guardrail_decisions") or [])
    decisions.append(result)
    return {**state, "final_answer": result.text, "guardrail_decisions": decisions}


async def node_judge(state: GraphState) -> GraphState:
    from agent.judge import judge_batch

    try:
        judge_batch([{
            "interaction_id": state["channel_message"].session_id,
            "response": state["final_answer"],
            "source_document_id": None,
        }])
    except Exception:
        logger.warning("judge_batch falhou, continuando", exc_info=True)
    await trace_interaction("NOC", state["channel_message"], {"node": "judge"})
    return state


# ---------------------------------------------------------------------------
# Lógica de roteamento condicional
# ---------------------------------------------------------------------------

def _after_guardrails(state: GraphState) -> str:
    return END if state["blocked"] else "routing_decision"


def _after_routing(state: GraphState) -> str:
    route = state.get("route", "supervisor_agent")
    _map = {
        "catalog_agent": "catalog_agent",
        "billing_agent": "billing",
        "cancellation_agent": "handoff_cancellation",
        "deals_agent": "handoff_deals",
        "eligibility_agent": "eligibility",
        "simulation_agent": "simulation",
        "supervisor_agent": "supervisor",
    }
    return _map.get(route, "supervisor")


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(GraphState)

    g.add_node("input_guardrails", node_input_guardrails)
    g.add_node("routing_decision", node_routing_decision)
    g.add_node("catalog_agent", node_catalog_agent)
    g.add_node("billing", node_billing)
    g.add_node("handoff_cancellation", node_handoff_cancellation)
    g.add_node("handoff_deals", node_handoff_deals)
    g.add_node("eligibility", node_eligibility)
    g.add_node("simulation", node_simulation)
    g.add_node("supervisor", node_supervisor)
    g.add_node("output_guardrails", node_output_guardrails)
    g.add_node("judge", node_judge)

    g.set_entry_point("input_guardrails")
    g.add_conditional_edges("input_guardrails", _after_guardrails)
    g.add_conditional_edges(
        "routing_decision",
        _after_routing,
        {
            "catalog_agent": "catalog_agent",
            "billing": "billing",
            "handoff_cancellation": "handoff_cancellation",
            "handoff_deals": "handoff_deals",
            "eligibility": "eligibility",
            "simulation": "simulation",
            "supervisor": "supervisor",
        },
    )
    for node in [
        "catalog_agent",
        "billing",
        "handoff_cancellation",
        "handoff_deals",
        "eligibility",
        "simulation",
        "supervisor",
    ]:
        g.add_edge(node, "output_guardrails")
    g.add_edge("output_guardrails", "judge")
    g.add_edge("judge", END)

    return g


_compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Entrypoint público
# ---------------------------------------------------------------------------

async def run_interaction(
    channel_message: ChannelMessage,
    config: dict | None = None,
) -> str:
    await trace_interaction("IC", channel_message, {"text": channel_message.text})

    t_inicio = time.perf_counter()

    initial_state = GraphState(
        channel_message=channel_message,
        sanitized_input="",
        route="",
        intent="",
        answer="",
        final_answer="",
        blocked=False,
        guardrail_decisions=[],
        chunk_id=None,
    )

    final_state = await _compiled_graph.ainvoke(initial_state, config=config or {})

    # Sumário de observabilidade ao final do fluxo — CRITERIOS-DE-ACEITE §6.
    # Agrega latência total, chunk usado e guardrails acionados numa linha legível.
    latencia_ms = int((time.perf_counter() - t_inicio) * 1000)
    log_sumario_interacao(
        channel_message=channel_message,
        latencia_ms=latencia_ms,
        chunk_id=final_state.get("chunk_id"),
        guardrail_decisions=final_state.get("guardrail_decisions") or [],
    )

    # Publica SUMARIO no broadcaster — Chainlit e SSE usam para finalizar o fluxo visual.
    from orchestrator.trace_broadcaster import get_broadcaster
    await get_broadcaster().publish({
        "type": "SUMARIO",
        "session_id": channel_message.session_id,
        "latencia_ms": latencia_ms,
        "chunk_id": final_state.get("chunk_id"),
    })

    return final_state.get("final_answer") or final_state.get("answer") or ""


# ---------------------------------------------------------------------------
# Helpers de negócio (portados de Kirllen, adaptados para async + ChannelMessage)
# ---------------------------------------------------------------------------

async def _run_catalog(text: str, msg: ChannelMessage) -> tuple[str, str | None]:
    """Consulta o catálogo RAG e chama o LLM com o contexto encontrado.

    Retorna (resposta, chunk_id) para que o AI Dev Sr propague o chunk_id
    ao estado do grafo e ao sumário de observabilidade (§6).

    Colaboração:
      - QueryResult vem de Ana (rag_pipeline/query_api.py)
      - build_prompt / not_found_response vem de Gustavo (agent/prompt.py)
      - complete() usa llm_client configurado pelo AI Dev Sr para Flow CI&T
    """
    try:
        from agent.llm_client import complete
        from agent.prompt import build_prompt, not_found_response
        from rag_pipeline.query_api import query
        from rag_pipeline.vectorizer import get_client

        chroma_client = get_client()
        # Decisão: get_client() usa path absoluto (vectorizer.py) para evitar
        # problema de cwd relativo quando o uvicorn muda de diretório.
        result = query(chroma_client, text)
        if not result.found:
            return not_found_response(), None
        prompt = build_prompt(text, result)
        if prompt is None:
            # build_prompt retorna None quando found=False — nunca deve chegar
            # aqui, mas tratamos por segurança (contrato de Gustavo).
            return not_found_response(), None
        return complete(prompt), result.chunk_id
    except Exception:
        logger.warning("catalog_agent falhou, usando fallback", exc_info=True)
        return "Não consegui acessar o catálogo no momento. Tente novamente.", None


async def _run_billing(msg: ChannelMessage) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            cliente = r.json()
        nome = cliente.get("nome", "cliente")
        plano = cliente.get("plano_atual", "seu plano")
        mensalidade = cliente.get("mensalidade", 0)
        return (
            f"Olá, {nome}! Sua fatura do {plano} é de R${mensalidade:.2f}. "
            "Posso enviar a segunda via por e-mail ou SMS. Qual prefere?"
        )
    except Exception:
        logger.warning("billing falhou", exc_info=True)
        return "Não consegui acessar as informações de fatura no momento."


async def _handoff(service: str, message: str, msg: ChannelMessage) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{MOCK_BASE}/agent/{service}/interact",
                json={"message": message, "conversation_id": msg.session_id},
            )
            return r.json().get("response", f"Handoff para {service} realizado.")
    except Exception:
        logger.warning("handoff %s falhou", service, exc_info=True)
        return f"Encaminhei sua solicitação para o time de {service}. Em breve entraremos em contato."


async def _run_eligibility(msg: ChannelMessage) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            r_eleg = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
            cliente = r_crm.json()
            elegibilidade = r_eleg.json()
        nome = cliente.get("nome", "cliente")
        if not elegibilidade.get("pode_trocar"):
            return f"Olá, {nome}! No momento não é possível realizar a troca de plano."
        planos = ", ".join(elegibilidade.get("planos_disponiveis", []))
        if elegibilidade.get("fidelidade_ativa"):
            return (
                f"Olá, {nome}! Você pode trocar, mas está em fidelidade até "
                f"{elegibilidade.get('fim_fidelidade')}. "
                f"Multa: R${elegibilidade.get('multa_cancelamento', 0):.2f}. "
                f"Planos disponíveis: {planos}."
            )
        return f"Olá, {nome}! Você está livre para trocar sem multa. Planos: {planos}."
    except Exception:
        logger.warning("eligibility falhou", exc_info=True)
        return "Não consegui verificar sua elegibilidade no momento."


async def _run_simulation(message: str, msg: ChannelMessage) -> str:
    plano_destino = _extrair_plano(message)
    if plano_destino is None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
                planos = ", ".join(r.json().get("planos_disponiveis", []))
            return f"Qual plano gostaria de simular? Disponíveis: {planos}."
        except (httpx.HTTPError, ValueError, KeyError):
            return "Qual plano gostaria de simular?"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{MOCK_BASE}/planos/simular-troca",
                json={"cpf": MOCK_CPF, "plano_destino": plano_destino},
            )
            data = r.json()
        if "erro" in data:
            return f"Não consegui simular: {data['erro']}"
        sinal = "+" if data["diferenca_mensal"] >= 0 else ""
        multa = (
            f" Multa de fidelidade: R${data['multa_se_aplicavel']:.2f}."
            if data.get("multa_se_aplicavel", 0) > 0
            else ""
        )
        return (
            f"Simulação: {data['plano_atual']} → {data['plano_destino']}. "
            f"Atual: R${data['mensalidade_atual']:.2f} | Nova: R${data['mensalidade_destino']:.2f} "
            f"({sinal}R${data['diferenca_mensal']:.2f}/mês).{multa} "
            f"Vigência a partir de {data['data_vigencia']}. Confirma?"
        )
    except Exception:
        logger.warning("simulation falhou", exc_info=True)
        return "Não consegui realizar a simulação no momento."


_PLANO_ALIAS = {
    "turbo 40": "turbo-40gb",
    "turbo 40gb": "turbo-40gb",
    "turbo-40gb": "turbo-40gb",
    "controle 50": "controle-50gb",
    "controle 50gb": "controle-50gb",
    "controle-50gb": "controle-50gb",
    "controle 100": "controle-100gb",
    "controle 100gb": "controle-100gb",
    "família prime": "familia-prime",
    "familia prime": "familia-prime",
    "familia-prime": "familia-prime",
    "pré-pago turbo": "pre-pago-turbo",
    "pre-pago turbo": "pre-pago-turbo",
}


def _extrair_plano(texto: str) -> str | None:
    texto = texto.lower()
    for alias, plano_id in _PLANO_ALIAS.items():
        if alias in texto:
            return plano_id
    return None
