"""Orquestrador LangGraph — AI Developer Sr (Igor Scaglia).

Responsabilidade: montar o grafo que une as fatias dos colegas usando
os contratos definidos em ARQUITETURA.md como cola entre as partes.

  Ana Carolina  → QueryResult      (rag_pipeline/query_api.py)
  Gustavo       → GuardrailResult  (agent/guardrails/)
  Kirllen       → ChannelMessage   (gateway/channel_gateway.py)
  Igor (este arquivo) → build_graph(), run_interaction(), helpers de negócio

Fluxo do grafo (PAPEIS-E-ENTREGAVEIS.md — AI Developer Sr):
  input_guardrails → routing_decision → [catalog|billing|cancellation|
  deals|eligibility|simulation|supervisor] → output_guardrails → judge → END

Expansão sobre o framework:
  O agent_platform_oci fornece EnterpriseRouter e ChannelMessage, mas NÃO
  monta o StateGraph — essa topologia (nós, arestas, condicionais) é
  responsabilidade explícita do AI Developer Sr (ver PAPEIS-E-ENTREGAVEIS.md).
"""

from __future__ import annotations

import asyncio
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

from orchestrator.tracer import log_sumario_interacao, trace_flow, trace_interaction

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
    channel_message: ChannelMessage   # mensagem original do canal (imutável no fluxo)
    sanitized_input: str              # texto após guardrail de input (PII mascarado)
    route: str                        # nome do agente escolhido pelo EnterpriseRouter
    intent: str                       # intenção detectada (catalog, billing, etc.)
    answer: str                       # resposta gerada pelo nó de domínio
    final_answer: str                 # resposta pós-guardrail de output
    blocked: bool                     # True se o guardrail de input bloqueou a mensagem
    guardrail_decisions: list[Any]    # lista de GuardrailResult (input + output)
    chunk_id: str | None              # id do chunk RAG usado (None se não consultou RAG)


# ---------------------------------------------------------------------------
# Helper: LLM com FLOW trace
# ---------------------------------------------------------------------------

async def _call_llm_and_trace(
    prompt: str,
    msg: ChannelMessage,
    system: str | None = None,
    model: str | None = None,
) -> str:
    """Chama o LLM emitindo FLOW ENTER/EXIT + evento LLM com latência e conteúdo.

    Wraps agent/llm_client.complete() para garantir que toda chamada ao modelo
    seja visível no Chainlit (step expansível) e auditável no log local.
    Re-raise como RuntimeError tipado para grep preciso: 'llm_complete_failed:'.

    Retry: em caso de APITimeoutError faz UMA segunda tentativa após 2s.
    Outros erros (bad request, auth) propagam imediatamente sem retry.
    """
    from agent.llm_client import complete

    await trace_flow("ENTER", "llm.complete", msg, {"prompt_len": len(prompt)})
    t0 = time.perf_counter()
    last_exc: Exception | None = None

    for attempt in range(2):
        try:
            result = complete(prompt, model=model, system=system)
            latencia_ms = int((time.perf_counter() - t0) * 1000)
            used_model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
            await trace_flow("EXIT", "llm.complete", msg, {
                "status": "OK",
                "latencia_ms": latencia_ms,
                "response_len": len(result),
                **({"retried": True} if attempt > 0 else {}),
            })
            # Evento LLM inclui prompt e resposta completos para auditoria no Chainlit
            await trace_interaction("LLM", msg, {
                "model": used_model,
                "prompt_len": len(prompt),
                "response_len": len(result),
                "latencia_ms": latencia_ms,
                "prompt": prompt,
                "response": result,
            })
            return result
        except Exception as exc:
            last_exc = exc
            # Retry apenas em timeout (transiente) e apenas na primeira tentativa
            if attempt == 0 and "APITimeoutError" in str(exc):
                logger.warning("LLM timeout (tentativa 1/2), retentando em 2s...")
                await asyncio.sleep(2)
                continue
            break

    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fecha step com ERROR antes de propagar — Chainlit exibe ❌
    await trace_flow("EXIT", "llm.complete", msg, {
        "status": "ERROR",
        "latencia_ms": latencia_ms,
        "error": f"{type(last_exc).__name__}: {last_exc}",
    })
    raise RuntimeError(f"llm_complete_failed: {type(last_exc).__name__}: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Nós do grafo
# ---------------------------------------------------------------------------

async def node_input_guardrails(state: GraphState) -> GraphState:
    """Aplica guardrail de input: mascara PII e decide se bloqueia a mensagem.

    Produz: sanitized_input (texto limpo), blocked (bool), guardrail_decisions[0].
    Quando blocked=True, preenche final_answer diretamente para que o gateway
    retorne uma resposta ao usuário sem percorrer o restante do grafo.
    """
    from agent.guardrails.input_guardrail import check_input
    from agent.models import Action

    msg = state["channel_message"]
    await trace_flow("ENTER", "node.input_guardrails", msg)
    result = check_input(msg.text)
    blocked = result.action_taken == Action.BLOCK
    await trace_interaction("GRL", msg, {
        "guardrail": "input", "violation": result.violation.value, "blocked": blocked,
    })
    await trace_flow("EXIT", "node.input_guardrails", msg, {
        "status": "OK", "blocked": blocked,
    })

    new_state = {
        **state,
        "sanitized_input": result.text,
        "blocked": blocked,
        "guardrail_decisions": [result],
    }
    # G8: quando bloqueado, preenche final_answer para o gateway não devolver ""
    # (_after_guardrails encaminha direto para END sem passar pelo restante do fluxo)
    if blocked:
        new_state["final_answer"] = (
            "Sua mensagem não pôde ser processada. "
            "Por favor, reformule sua pergunta."
        )
    return new_state


async def node_routing_decision(state: GraphState) -> GraphState:
    """Detecta a intenção e escolhe o agente de domínio via EnterpriseRouter.

    O router usa regras determinísticas (YAML), não LLM.
    Produz: route (nome do agente, ex: "catalog_agent"), intent (ex: "catalog").
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.routing_decision", msg)
    decision = await _router.route({"sanitized_input": state["sanitized_input"]})
    await trace_interaction("NOC", msg, {
        "node": "routing_decision",
        "intent": decision.intent,
        "agent": decision.agent,
        # Inclui o texto sanitizado para auditoria do roteamento no Chainlit (SUG-03)
        "sanitized_input": state["sanitized_input"][:120],
    })
    await trace_flow("EXIT", "node.routing_decision", msg, {
        "status": "OK", "intent": decision.intent, "agent": decision.agent,
    })
    return {**state, "route": decision.agent, "intent": decision.intent}


async def node_catalog_agent(state: GraphState) -> GraphState:
    """Consulta o catálogo RAG e gera resposta via LLM com o contexto encontrado.

    Produz: answer (resposta gerada), chunk_id (id do chunk RAG ou None).
    Usa _run_catalog() que orquestra RAG (Ana) + LLM (Gustavo).
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.catalog_agent", msg)
    t0 = time.perf_counter()
    answer, chunk_id = await _run_catalog(state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado pela heurística: chunk_id ausente + resposta de indisponibilidade
    is_fallback = chunk_id is None and "momento" in answer
    await trace_interaction("NOC", msg, {"node": "catalog_agent", "chunk_id": chunk_id})
    await trace_flow("EXIT", "node.catalog_agent", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        "chunk_id": chunk_id,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer, "chunk_id": chunk_id}


async def node_billing(state: GraphState) -> GraphState:
    """Consulta o CRM mock e gera resposta sobre fatura/cobranças via LLM.

    Produz: answer (resposta sobre dados de fatura do cliente).
    Usa CPF fixo MOCK_CPF — no projeto real o CPF vem do contexto de sessão.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.billing", msg)
    t0 = time.perf_counter()
    answer = await _run_billing(msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado pela palavra "momento" na resposta de indisponibilidade
    is_fallback = "momento" in answer
    await trace_interaction("NOC", msg, {"node": "billing"})
    await trace_flow("EXIT", "node.billing", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer}


async def node_handoff_cancellation(state: GraphState) -> GraphState:
    """Encaminha solicitação de cancelamento para o agente mock externo.

    Produz: answer (confirmação de handoff ou fallback textual).
    Handoff real POST /agent/cancellation/interact em mock_services.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.handoff_cancellation", msg)
    t0 = time.perf_counter()
    answer = await _handoff("cancellation", state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado pela frase padrão do _handoff em caso de exceção HTTP
    is_fallback = "Em breve entraremos em contato" in answer
    await trace_interaction("NOC", msg, {"node": "handoff_cancellation"})
    await trace_flow("EXIT", "node.handoff_cancellation", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer}


async def node_handoff_deals(state: GraphState) -> GraphState:
    """Encaminha solicitação de negociação/ofertas para o agente mock externo.

    Produz: answer (confirmação de handoff ou fallback textual).
    Handoff real POST /agent/deals/interact em mock_services.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.handoff_deals", msg)
    t0 = time.perf_counter()
    answer = await _handoff("deals", state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado pela frase padrão do _handoff em caso de exceção HTTP
    is_fallback = "Em breve entraremos em contato" in answer
    await trace_interaction("NOC", msg, {"node": "handoff_deals"})
    await trace_flow("EXIT", "node.handoff_deals", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer}


async def node_eligibility(state: GraphState) -> GraphState:
    """Consulta CRM + elegibilidade mock e gera resposta sobre troca de plano via LLM.

    Produz: answer (resposta sobre elegibilidade do cliente).
    Faz duas chamadas HTTP ao mock_services: /crm/cliente e /crm/cliente/elegibilidade.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.eligibility", msg)
    t0 = time.perf_counter()
    answer = await _run_eligibility(msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado pela palavra "momento" na resposta de indisponibilidade
    is_fallback = "momento" in answer
    await trace_interaction("NOC", msg, {"node": "eligibility"})
    await trace_flow("EXIT", "node.eligibility", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer}


async def node_simulation(state: GraphState) -> GraphState:
    """Simula troca de plano consultando mock_services e gerando resposta via LLM.

    Dois caminhos:
      1. Plano identificado na mensagem → POST /planos/simular-troca com dados reais.
      2. Plano não identificado → consulta elegibilidade para listar opções disponíveis.

    Produz: answer (resultado da simulação ou solicitação de clarificação).
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.simulation", msg)
    t0 = time.perf_counter()
    answer = await _run_simulation(state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    # Fallback detectado por "momento" + "simul" juntos na resposta de indisponibilidade
    is_fallback = "momento" in answer and "simul" in answer
    await trace_interaction("NOC", msg, {"node": "simulation"})
    await trace_flow("EXIT", "node.simulation", msg, {
        "status": "ERROR" if is_fallback else "OK",
        "latencia_ms": latencia_ms,
        **({"fallback": True} if is_fallback else {}),
    })
    return {**state, "answer": answer}


async def node_supervisor(state: GraphState) -> GraphState:
    """Agente supervisor: responde perguntas fora dos domínios específicos via LLM.

    Usado como fallback quando nenhuma intenção específica é detectada pelo router.
    Produz: answer (resposta genérica de assistente TIM).
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.supervisor", msg)
    await trace_interaction("NOC", msg, {"node": "supervisor"})
    try:
        from agent.prompt import build_supervisor_prompt, build_system_prompt
        prompt = build_supervisor_prompt(msg.text)
        answer = await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
        await trace_flow("EXIT", "node.supervisor", msg, {"status": "OK"})
    except Exception as exc:
        # LLM falhou: entrega resposta de boas-vindas genérica em vez de propagar erro
        logger.warning("supervisor LLM falhou, usando fallback", exc_info=True)
        answer = (
            "Olá! Sou o assistente TIM. Posso ajudar com planos, fatura, "
            "cancelamento ou negociação. Como posso te ajudar?"
        )
        await trace_flow("EXIT", "node.supervisor", msg, {
            "status": "ERROR",
            "fallback": True,
            "error": f"{type(exc).__name__}: {exc}",
        })
    return {**state, "answer": answer}


async def node_output_guardrails(state: GraphState) -> GraphState:
    """Aplica guardrail de output: sanitiza e valida a resposta antes de entregá-la.

    Produz: final_answer (resposta sanitizada), guardrail_decisions atualizado
    com o segundo resultado (output) adicionado à lista existente (input).
    """
    from agent.guardrails.output_guardrail import check_output

    msg = state["channel_message"]
    await trace_flow("ENTER", "node.output_guardrails", msg)
    result = check_output(state["answer"])
    await trace_interaction("GRL", msg, {
        "guardrail": "output", "violation": result.violation.value,
    })
    await trace_flow("EXIT", "node.output_guardrails", msg, {"status": "OK"})
    # Preserva a lista imutavelmente: cria nova lista a partir da existente + novo resultado
    decisions = list(state.get("guardrail_decisions") or [])
    decisions.append(result)
    return {**state, "final_answer": result.text, "guardrail_decisions": decisions}


async def node_judge(state: GraphState) -> GraphState:
    """Avalia a qualidade da resposta final offline via judge_batch (Gustavo).

    Não modifica o estado — apenas emite evento JUDGE com os resultados.
    expects_source=True somente para catalog_agent, pois outros domínios
    (billing, eligibility, etc.) não usam RAG e não têm chunk_id esperado —
    judge_batch() usa esse campo para não marcar como alucinação/dado
    fabricado uma resposta CRM legítima sem chunk_id, e para não marcar
    como alucinação um "não encontrei" genuíno do catalog_agent.
    """
    from agent.judge import judge_batch

    msg = state["channel_message"]
    await trace_flow("ENTER", "node.judge", msg)
    items = [{
        "interaction_id": msg.session_id,
        "question": state.get("sanitized_input"),
        "response": state["final_answer"],
        "source_document_id": state.get("chunk_id"),
        # Apenas catalog_agent usa RAG; outros domínios não têm fonte esperada
        "expects_source": state.get("route") == "catalog_agent",
    }]
    try:
        findings = judge_batch(items)
        # Filtra apenas itens sinalizados para incluir os motivos no evento
        flagged = [f for f in findings if f.flagged]
        await trace_interaction("JUDGE", msg, {
            "n_itens": len(items),
            "flagged": len(flagged),
            "status": "OK",
            **({"reasons": flagged[0].reasons} if flagged else {}),
        })
        await trace_flow("EXIT", "node.judge", msg, {"status": "OK"})
    except Exception:
        # judge_batch falhou: não bloqueia o fluxo — resposta já foi entregue
        logger.warning("judge_batch falhou, continuando", exc_info=True)
        await trace_interaction("JUDGE", msg, {"n_itens": len(items), "status": "ERROR"})
        await trace_flow("EXIT", "node.judge", msg, {"status": "ERROR", "fallback": True})
    await trace_interaction("NOC", msg, {"node": "judge"})
    # Retorna state inalterado — judge é somente leitura
    return state


# ---------------------------------------------------------------------------
# Lógica de roteamento condicional (arestas condicionais do StateGraph)
# ---------------------------------------------------------------------------

def _after_guardrails(state: GraphState) -> str:
    """Aresta após input_guardrails: encerra em END se bloqueado, prossegue se não.

    Quando blocked=True, final_answer já foi preenchido pelo nó e o gateway
    devolve a mensagem padrão diretamente, sem acionar o LLM.
    """
    return END if state["blocked"] else "routing_decision"


def _after_routing(state: GraphState) -> str:
    """Aresta após routing_decision: mapeia o nome do agente (router) ao nó do grafo.

    O EnterpriseRouter retorna chaves no formato '{domínio}_agent'
    (ex: "billing_agent"), enquanto os nós do grafo usam o nome curto
    (ex: "billing"). O mapa abaixo faz essa tradução. Rota desconhecida
    cai em "supervisor" como fallback seguro.
    """
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
    """Monta a topologia do StateGraph com 11 nós e 3 arestas condicionais.

    Topologia:
      input_guardrails → (condicional: blocked → END | → routing_decision)
      routing_decision → (condicional: route → nó de domínio correspondente)
      [todos os domínios] → output_guardrails → judge → END
    """
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
    # Todos os nós de domínio convergem para output_guardrails (fanin)
    for node in [
        "catalog_agent", "billing", "handoff_cancellation",
        "handoff_deals", "eligibility", "simulation", "supervisor",
    ]:
        g.add_edge(node, "output_guardrails")
    g.add_edge("output_guardrails", "judge")
    g.add_edge("judge", END)

    return g


_compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Helpers de serialização de estado (para eventos STATE / GRAPH / ORCH)
# ---------------------------------------------------------------------------

def _serialize_guardrail(r: Any) -> dict:
    """Converte um GuardrailResult em dict JSON-safe sem importar Action/Violation.

    Usa getattr introspectivo para não criar dependência circular com agent.models.
    """
    action_str = str(getattr(r, "action_taken", "")).lower()
    return {
        "type": getattr(r, "guardrail_type", "?"),
        "violation": getattr(getattr(r, "violation", None), "value", "?"),
        # "block" é substring tanto de "Action.BLOCK" quanto de "block"
        "blocked": "block" in action_str,
    }


def _state_snapshot(state: dict, include_empty: bool = False) -> dict:
    """Serializa os campos visíveis do GraphState excluindo channel_message.

    include_empty=True: inclui campos com valor default (usado para estado inicial).
    include_empty=False (padrão): omite strings vazias, False e None (estado final).
    guardrail_decisions é sempre serializado quando presente.
    """
    result = {}
    for k in ("sanitized_input", "route", "intent", "answer", "final_answer", "blocked", "chunk_id"):
        v = state.get(k)
        # Omite valores default quando include_empty=False para reduzir ruído
        if not include_empty and (v is None or v == "" or v is False):
            continue
        result[k] = (v[:120] + "…") if isinstance(v, str) and len(v) > 120 else v
    decisions = state.get("guardrail_decisions") or []
    if include_empty or decisions:
        result["guardrail_decisions"] = [_serialize_guardrail(r) for r in decisions]
    return result


def _state_delta(prev: dict, current: dict) -> dict:
    """Retorna apenas os campos que mudaram entre dois snapshots do estado.

    Exclui channel_message (objeto não-serializável e imutável no fluxo).
    Necessário porque astream(stream_mode='updates') entrega o retorno
    completo do nó (todos os campos via {**state, ...}), não apenas o delta —
    sem esta função o evento STATE mostraria todos os campos a cada nó.
    """
    changed = {}
    for k, curr_v in current.items():
        # channel_message não é serializável e nunca muda
        if k == "channel_message":
            continue
        # Inclui somente campos cujo valor efetivamente mudou
        if curr_v == prev.get(k):
            continue
        if k == "guardrail_decisions":
            changed[k] = [_serialize_guardrail(r) for r in (curr_v or [])]
        elif isinstance(curr_v, str) and len(curr_v) > 120:
            changed[k] = curr_v[:120] + "…"
        else:
            changed[k] = curr_v
    return changed


# ---------------------------------------------------------------------------
# Entrypoint público
# ---------------------------------------------------------------------------

async def run_interaction(
    channel_message: ChannelMessage,
    config: dict | None = None,
) -> str:
    """Executa o grafo completo para uma mensagem e retorna a resposta final.

    Fluxo:
      1. IC  — ancora a sessão no tracer
      2. GRAPH — registra topologia e estado inicial (antes da execução)
      3. astream — percorre os nós, emitindo STATE após cada mudança de estado
      4. ORCH — registra resultado, rota, latência e estado final

    Usa astream(stream_mode='updates') em vez de ainvoke para interceptar
    o delta de estado após cada nó sem alterar a lógica dos próprios nós.
    """
    await trace_interaction("IC", channel_message, {"text": channel_message.text})

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

    # GRAPH emitido antes de iniciar o grafo — ancora o estado inicial na UI
    await trace_interaction("GRAPH", channel_message, {
        "graph_nodes": 11,
        "entry_point": "input_guardrails",
        "compiled": True,
        "initial_state": _state_snapshot(initial_state, include_empty=True),
    })

    t_inicio = time.perf_counter()

    # Acumula o estado atual em dict mutável para calcular deltas entre nós
    current: dict = dict(initial_state)
    async for chunk in _compiled_graph.astream(initial_state, config=config or {}, stream_mode="updates"):
        # chunk = {node_name: node_return_value} — um por nó concluído
        for node_name, node_delta in chunk.items():
            # Nós internos do LangGraph (ex: "__start__") não têm semântica de domínio
            if node_name.startswith("__"):
                continue
            prev = dict(current)
            current.update(node_delta)
            delta = _state_delta(prev, current)
            # Emite STATE apenas quando há campos que efetivamente mudaram
            if delta:
                await trace_interaction("STATE", channel_message, {
                    "node": node_name,
                    "delta": delta,
                })

    final_state = current
    latencia_ms = int((time.perf_counter() - t_inicio) * 1000)
    log_sumario_interacao(
        channel_message=channel_message,
        latencia_ms=latencia_ms,
        chunk_id=final_state.get("chunk_id"),
        guardrail_decisions=final_state.get("guardrail_decisions") or [],
    )

    await trace_interaction("ORCH", channel_message, {
        "route": final_state.get("route"),
        "intent": final_state.get("intent"),
        "rag_hit": final_state.get("chunk_id") is not None,
        "blocked": final_state.get("blocked", False),
        "latencia_ms": latencia_ms,
        "guardrails_triggered": len(final_state.get("guardrail_decisions") or []),
        "final_state": _state_snapshot(final_state),
    })

    # Prioriza final_answer (pós-guardrail); fallback para answer (pré-guardrail)
    return final_state.get("final_answer") or final_state.get("answer") or ""


# ---------------------------------------------------------------------------
# Helpers de negócio
# ---------------------------------------------------------------------------

async def _run_catalog(text: str, msg: ChannelMessage) -> tuple[str, str | None]:
    """Consulta o catálogo RAG e chama o LLM com o contexto encontrado.

    Colaboração entre fatias:
      - QueryResult vem de Ana (rag_pipeline/query_api.py)
      - build_prompt / not_found_response / build_not_found_prompt vêm de Gustavo (agent/prompt.py)
      - _call_llm_and_trace é responsabilidade do AI Dev Sr (este arquivo)

    Dois caminhos:
      - RAG hit  → build_prompt + LLM com contexto do chunk
      - RAG miss → build_not_found_prompt + LLM sem contexto (resposta honesta de não encontrado)
    """
    try:
        from agent.prompt import build_prompt, not_found_response
        from rag_pipeline.query_api import query
        from rag_pipeline.vectorizer import get_client

        await trace_flow("ENTER", "rag.query", msg)
        t0 = time.perf_counter()
        chroma_client = get_client()
        result = query(chroma_client, text)
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", "rag.query", msg, {
            "status": "OK", "found": result.found,
            "chunk_id": result.chunk_id, "latencia_ms": latencia_ms,
        })
        await trace_interaction("RAG", msg, {
            "found": result.found,
            "chunk_id": result.chunk_id,
            "score": getattr(result, "confidence_score", None),
            "latencia_ms": latencia_ms,
        })

        if not result.found:
            # RAG miss: responde honestamente sem inventar dados do catálogo
            from agent.prompt import build_not_found_prompt, build_system_prompt
            prompt = build_not_found_prompt(text)
            response = await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
            return response, None

        await trace_flow("ENTER", "prompt.build", msg)
        prompt = build_prompt(text, result)
        await trace_flow("EXIT", "prompt.build", msg, {"status": "OK"})

        if prompt is None:
            # build_prompt retornou None (resultado inválido): fallback sem LLM
            return not_found_response(), None

        response = await _call_llm_and_trace(prompt, msg)
        return response, result.chunk_id
    except Exception as exc:
        logger.warning("catalog_agent falhou, usando fallback", exc_info=True)
        await trace_flow("EXIT", "rag.query", msg, {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        })
        return "Não consegui acessar o catálogo no momento. Tente novamente.", None


async def _run_billing(msg: ChannelMessage) -> str:
    """Consulta dados do cliente no CRM mock e gera resposta sobre fatura via LLM.

    Usa CPF fixo MOCK_CPF (hardcoded para a PoC — no real viria da sessão autenticada).
    """
    try:
        await trace_flow("ENTER", "mock.crm", msg, {"endpoint": f"/crm/cliente/{MOCK_CPF}"})
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            cliente = r.json()
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", "mock.crm", msg, {
            "status": "OK", "http_status": r.status_code, "latencia_ms": latencia_ms,
        })
        await trace_interaction("MOCK", msg, {
            "service": "crm", "endpoint": f"/crm/cliente/{MOCK_CPF}",
            "http_status": r.status_code, "latencia_ms": latencia_ms, "owner": "KIRLLEN",
        })
        from agent.prompt import build_crm_prompt, build_system_prompt
        prompt = build_crm_prompt(msg.text, "billing", cliente)
        return await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
    except Exception as exc:
        logger.warning("billing falhou", exc_info=True)
        await trace_flow("EXIT", "mock.crm", msg, {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        })
        return "Não consegui acessar as informações de fatura no momento."


async def _handoff(service: str, message: str, msg: ChannelMessage) -> str:
    """Encaminha mensagem para um agente mock externo via POST.

    Usado por cancellation e deals. O agente mock responde com uma confirmação
    de atendimento. Em caso de falha HTTP, retorna fallback textual genérico.
    """
    endpoint = f"/agent/{service}/interact"
    component = f"mock.{service}"
    try:
        await trace_flow("ENTER", component, msg, {"endpoint": endpoint, "service": service})
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{MOCK_BASE}{endpoint}",
                json={"message": message, "conversation_id": msg.session_id},
            )
            response = r.json().get("response", f"Handoff para {service} realizado.")
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", component, msg, {
            "status": "OK", "http_status": r.status_code, "latencia_ms": latencia_ms,
        })
        await trace_interaction("MOCK", msg, {
            "service": service, "endpoint": endpoint,
            "http_status": r.status_code, "latencia_ms": latencia_ms, "owner": "KIRLLEN",
        })
        return response
    except Exception as exc:
        logger.warning("handoff %s falhou", service, exc_info=True)
        # Fecha o step com ERROR antes do fallback para Chainlit exibir ❌
        await trace_flow("EXIT", component, msg, {
            "status": "ERROR",
            "fallback": True,
            "error": f"{type(exc).__name__}: {exc}",
        })
        return f"Encaminhei sua solicitação para o time de {service}. Em breve entraremos em contato."


async def _run_eligibility(msg: ChannelMessage) -> str:
    """Consulta CRM e elegibilidade do cliente e gera resposta via LLM.

    Faz duas chamadas HTTP paralelas ao mock_services:
      GET /crm/cliente/{cpf}             → dados do cliente
      GET /crm/cliente/{cpf}/elegibilidade → planos disponíveis para troca

    Nota: as chamadas são iniciadas em paralelo (dentro do mesmo client) mas
    awaited em sequência. Ambas são rastreadas individualmente no broadcaster.
    """
    try:
        await trace_flow("ENTER", "mock.crm", msg, {"endpoint": f"/crm/cliente/{MOCK_CPF}"})
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            r_eleg = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
        latencia_ms_crm = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", "mock.crm", msg, {
            "status": "OK", "http_status": r_crm.status_code, "latencia_ms": latencia_ms_crm,
        })
        await trace_interaction("MOCK", msg, {
            "service": "crm", "endpoint": f"/crm/cliente/{MOCK_CPF}",
            "http_status": r_crm.status_code, "latencia_ms": latencia_ms_crm, "owner": "KIRLLEN",
        })
        await trace_flow("ENTER", "mock.elegibilidade", msg, {
            "endpoint": f"/crm/cliente/{MOCK_CPF}/elegibilidade",
        })
        await trace_flow("EXIT", "mock.elegibilidade", msg, {
            "status": "OK", "http_status": r_eleg.status_code,
        })
        await trace_interaction("MOCK", msg, {
            "service": "elegibilidade", "endpoint": f"/crm/cliente/{MOCK_CPF}/elegibilidade",
            "http_status": r_eleg.status_code, "owner": "KIRLLEN",
        })
        api_data = {"cliente": r_crm.json(), "elegibilidade": r_eleg.json()}
        from agent.prompt import build_crm_prompt, build_system_prompt
        prompt = build_crm_prompt(msg.text, "eligibility", api_data)
        return await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
    except Exception as exc:
        logger.warning("eligibility falhou", exc_info=True)
        await trace_flow("EXIT", "mock.crm", msg, {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        })
        return "Não consegui verificar sua elegibilidade no momento."


async def _run_simulation(message: str, msg: ChannelMessage) -> str:
    """Simula troca de plano usando mock_services/planos/simular-troca.

    Dois caminhos baseados na presença do plano destino na mensagem:
      1. Plano identificado → POST /planos/simular-troca com {cpf, plano_destino}
      2. Plano não identificado → GET elegibilidade para listar opções + LLM de clarificação
    """
    plano_destino = _extrair_plano(message)

    if plano_destino is None:
        # Caminho de clarificação: usuário não especificou o plano destino
        try:
            await trace_flow("ENTER", "mock.elegibilidade", msg, {
                "endpoint": f"/crm/cliente/{MOCK_CPF}/elegibilidade",
            })
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
            latencia_ms = int((time.perf_counter() - t0) * 1000)
            await trace_flow("EXIT", "mock.elegibilidade", msg, {
                "status": "OK", "http_status": r.status_code, "latencia_ms": latencia_ms,
            })
            await trace_interaction("MOCK", msg, {
                "service": "elegibilidade", "endpoint": f"/crm/cliente/{MOCK_CPF}/elegibilidade",
                "http_status": r.status_code, "latencia_ms": latencia_ms, "owner": "KIRLLEN",
            })
            from agent.prompt import build_crm_prompt, build_system_prompt
            context = {"planos_disponiveis": r.json().get("planos_disponiveis", [])}
            prompt = build_crm_prompt(msg.text, "simulation_clarification", context)
            return await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
        except (httpx.HTTPError, ValueError, KeyError):
            # Falha HTTP ou JSON inválido: clarificação mínima sem LLM
            return "Qual plano gostaria de simular?"

    # Caminho de simulação: plano identificado, consulta mock de simulação
    try:
        endpoint = "/planos/simular-troca"
        await trace_flow("ENTER", "mock.simular_troca", msg, {"endpoint": endpoint})
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{MOCK_BASE}{endpoint}",
                json={"cpf": MOCK_CPF, "plano_destino": plano_destino},
            )
            data = r.json()
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", "mock.simular_troca", msg, {
            "status": "OK", "http_status": r.status_code, "latencia_ms": latencia_ms,
        })
        await trace_interaction("MOCK", msg, {
            "service": "simular_troca", "endpoint": endpoint,
            "http_status": r.status_code, "latencia_ms": latencia_ms, "owner": "KIRLLEN",
        })
        if "erro" in data:
            # API retornou erro de negócio (ex.: plano inválido ou inelegível)
            return f"Não consegui simular: {data['erro']}"
        from agent.prompt import build_crm_prompt, build_system_prompt
        prompt = build_crm_prompt(message, "simulation", data)
        return await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
    except Exception as exc:
        logger.warning("simulation falhou", exc_info=True)
        await trace_flow("EXIT", "mock.simular_troca", msg, {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        })
        return "Não consegui realizar a simulação no momento."


# Aliases para normalizar variações da grafia dos nomes de planos
# usados na extração por substring em _extrair_plano
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
    """Extrai o identificador canônico do plano destino a partir do texto livre.

    Faz matching por substring case-insensitive usando _PLANO_ALIAS.
    Retorna None se nenhum alias for encontrado — indica que o usuário
    não especificou o plano e o fluxo de clarificação deve ser acionado.
    """
    texto = texto.lower()
    for alias, plano_id in _PLANO_ALIAS.items():
        if alias in texto:
            return plano_id
    # Nenhum alias encontrado: plano destino não foi identificado
    return None
