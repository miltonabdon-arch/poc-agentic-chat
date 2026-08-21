"""Orquestrador LangGraph — AI Developer Sr (Igor Scaglia).

Responsabilidade: montar o grafo que une as fatias dos colegas usando
os contratos definidos em ARQUITETURA.md como cola entre as partes.

  Ana Carolina  → QueryResult      (rag_pipeline/query_api.py)
  Gustavo       → GuardrailResult  (agent/guardrails/)
  Kirllen       → ChannelMessage   (gateway/channel_gateway.py)
  Igor (este arquivo) → build_graph(), run_interaction(), helpers de negócio

Fluxo do grafo (PAPEIS-E-ENTREGAVEIS.md — AI Developer Sr / Escopo v1.2):
  input_guardrails → routing_decision → [informacao|cancelamento_retencao|
  ativacao|mudanca_plano|supervisor] → output_guardrails → judge → END

  Jornada informacao: catálogo TIM X + subcaso cobrança (fatura/segunda via)
  Jornada cancelamento_retencao: retenção CAN-01..05 + ATH
  Jornada ativacao: Crivo/Score + Catálogo Pré (sem handoff)
  Jornada mudanca_plano: elegibilidade + simulação unificadas

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
    intent: str                       # intenção detectada (informacao, cancelamento, etc.)
    answer: str                       # resposta gerada pelo nó de domínio
    final_answer: str                 # resposta pós-guardrail de output
    blocked: bool                     # True se o guardrail de input bloqueou a mensagem
    guardrail_decisions: list[Any]    # lista de GuardrailResult (input + output)
    chunk_id: str | None              # id do chunk RAG usado (None se não consultou RAG)
    handoff_origem: str | None        # "agente_contas" pula elegibilidade em mudanca_plano
    protocolo_id: str | None          # gerado pelo node_judge ao final do fluxo


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

    Retry: em caso de APITimeoutError faz UMA segunda tentativa após 2s.
    Outros erros propagam imediatamente sem retry.
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
            if attempt == 0 and "APITimeoutError" in str(exc):
                logger.warning("LLM timeout (tentativa 1/2), retentando em 2s...")
                await asyncio.sleep(2)
                continue
            break

    latencia_ms = int((time.perf_counter() - t0) * 1000)
    await trace_flow("EXIT", "llm.complete", msg, {
        "status": "ERROR",
        "latencia_ms": latencia_ms,
        "error": f"{type(last_exc).__name__}: {last_exc}",
    })
    raise RuntimeError(f"llm_complete_failed: {type(last_exc).__name__}: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Helper: detecção de subcaso cobrança dentro da jornada de Informação
# ---------------------------------------------------------------------------

_PALAVRAS_COBRANCA = frozenset({
    "fatura", "boleto", "pagamento", "vencimento",
    "segunda via", "débito automático", "cobrança",
})


def _eh_subcaso_cobranca(text: str) -> bool:
    """Retorna True se o texto indica dúvida de fatura/cobrança."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _PALAVRAS_COBRANCA)


# ---------------------------------------------------------------------------
# Nós do grafo — Escopo v1.2
# ---------------------------------------------------------------------------

async def node_input_guardrails(state: GraphState) -> GraphState:
    """Aplica guardrail de input: mascara PII e decide se bloqueia a mensagem."""
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
    if blocked:
        new_state["final_answer"] = (
            "Sua mensagem não pôde ser processada. "
            "Por favor, reformule sua pergunta."
        )
    return new_state


async def node_routing_decision(state: GraphState) -> GraphState:
    """Detecta a intenção e escolhe o agente de domínio via EnterpriseRouter."""
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.routing_decision", msg)
    decision = await _router.route({"sanitized_input": state["sanitized_input"]})
    await trace_interaction("NOC", msg, {
        "node": "routing_decision",
        "intent": decision.intent,
        "agent": decision.agent,
        "sanitized_input": state["sanitized_input"][:120],
    })
    await trace_flow("EXIT", "node.routing_decision", msg, {
        "status": "OK", "intent": decision.intent, "agent": decision.agent,
    })
    return {**state, "route": decision.agent, "intent": decision.intent}


async def node_informacao(state: GraphState) -> GraphState:
    """Jornada de Informação (Escopo v1.2 § 3.1).

    Detecta internamente se é subcaso cobrança (fatura/segunda via) antes de
    consultar o catálogo RAG. O subcaso cobrança consulta o CRM primeiro para
    identificar contrato e segmento do cliente.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.informacao", msg)
    t0 = time.perf_counter()

    if _eh_subcaso_cobranca(state["sanitized_input"]):
        answer = await _run_subcaso_cobranca(state["sanitized_input"], msg)
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_interaction("NOC", msg, {"node": "informacao", "subcaso": "cobrança"})
        await trace_flow("EXIT", "node.informacao", msg, {
            "status": "OK", "subcaso": "cobrança", "latencia_ms": latencia_ms,
        })
        return {**state, "answer": answer}

    answer, chunk_id = await _run_catalog(state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    await trace_interaction("NOC", msg, {
        "node": "informacao", "subcaso": "catalog", "chunk_id": chunk_id,
    })
    await trace_flow("EXIT", "node.informacao", msg, {
        "status": "OK", "subcaso": "catalog", "chunk_id": chunk_id, "latencia_ms": latencia_ms,
    })
    return {**state, "answer": answer, "chunk_id": chunk_id}


async def node_cancelamento_retencao(state: GraphState) -> GraphState:
    """Jornada de Cancelamento — retenção e reversão (Escopo v1.2 § 3.4).

    CAN-01: Catálogo de Retenção.
    CAN-02: Apresentação de contra-oferta de retenção.
    CAN-03: Catálogo de Reversão (cliente que já cancelou e quer voltar atrás).
    CAN-04: Isenção de multa incluída na oferta quando elegível.
    CAN-05: Transbordo para ATH apenas em exceção negocial (sem ofertas disponíveis).
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.cancelamento_retencao", msg)
    t0 = time.perf_counter()
    answer = await _run_cancelamento_retencao(state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    await trace_interaction("NOC", msg, {"node": "cancelamento_retencao"})
    await trace_flow("EXIT", "node.cancelamento_retencao", msg, {
        "status": "OK", "latencia_ms": latencia_ms,
    })
    return {**state, "answer": answer}


async def node_ativacao(state: GraphState) -> GraphState:
    """Jornada de Ativação — migração Pré-pago → Controle (Escopo v1.2 § 3.2 & 10).

    Sem handoff externo: consulta Crivo/Score e Catálogo de Ofertas Pré
    diretamente nesta jornada, sem acionar agente externo.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.ativacao", msg)
    t0 = time.perf_counter()
    answer = await _run_ativacao(state["sanitized_input"], msg)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    await trace_interaction("NOC", msg, {"node": "ativacao"})
    await trace_flow("EXIT", "node.ativacao", msg, {
        "status": "OK", "latencia_ms": latencia_ms,
    })
    return {**state, "answer": answer}


async def node_mudanca_plano(state: GraphState) -> GraphState:
    """Jornada de Mudança de Plano — Up/Down (Escopo v1.2 § 3.3).

    Elegibilidade e simulação são etapas sequenciais do mesmo fluxo.
    Subfluxo Contas: quando handoff_origem == "agente_contas", pula a etapa de
    elegibilidade e vai direto para simulação/aplicação do plano.
    """
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.mudanca_plano", msg)
    t0 = time.perf_counter()
    answer = await _run_mudanca_plano(
        state["sanitized_input"],
        msg,
        state.get("handoff_origem"),
    )
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    await trace_interaction("NOC", msg, {
        "node": "mudanca_plano", "handoff_origem": state.get("handoff_origem"),
    })
    await trace_flow("EXIT", "node.mudanca_plano", msg, {
        "status": "OK", "latencia_ms": latencia_ms,
    })
    return {**state, "answer": answer}


async def node_supervisor(state: GraphState) -> GraphState:
    """Agente supervisor: responde perguntas fora dos domínios específicos via LLM."""
    msg = state["channel_message"]
    await trace_flow("ENTER", "node.supervisor", msg)
    await trace_interaction("NOC", msg, {"node": "supervisor"})
    try:
        from agent.prompt import build_supervisor_prompt, build_system_prompt
        prompt = build_supervisor_prompt(state["sanitized_input"])
        answer = await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
        await trace_flow("EXIT", "node.supervisor", msg, {"status": "OK"})
    except Exception as exc:
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
    """Aplica guardrail de output: sanitiza e valida a resposta antes de entregá-la."""
    from agent.guardrails.output_guardrail import check_output

    msg = state["channel_message"]
    await trace_flow("ENTER", "node.output_guardrails", msg)
    result = check_output(state["answer"], intent=state.get("intent"))
    await trace_interaction("GRL", msg, {
        "guardrail": "output", "violation": result.violation.value,
    })
    await trace_flow("EXIT", "node.output_guardrails", msg, {"status": "OK"})
    decisions = list(state.get("guardrail_decisions") or [])
    decisions.append(result)
    return {**state, "final_answer": result.text, "guardrail_decisions": decisions}


async def node_judge(state: GraphState) -> GraphState:
    """Avalia a qualidade da resposta final offline via judge_batch."""
    from agent.judge import judge_batch

    session_id = state["channel_message"].session_id
    protocolo_id = f"PROT-{session_id[:8].upper()}"

    msg = state["channel_message"]
    await trace_flow("ENTER", "node.judge", msg)
    items = [{
        "interaction_id": msg.session_id,
        "question": state.get("sanitized_input"),
        "response": state["final_answer"],
        "source_document_id": state.get("chunk_id"),
        "expects_source": state.get("route") == "informacao_agent",
    }]
    try:
        findings = judge_batch(items)
        flagged = [f for f in findings if f.flagged]
        await trace_interaction("JUDGE", msg, {
            "n_itens": len(items),
            "flagged": len(flagged),
            "status": "OK",
            **({"reasons": flagged[0].reasons} if flagged else {}),
        })
        await trace_flow("EXIT", "node.judge", msg, {"status": "OK"})
    except Exception:
        logger.warning("judge_batch falhou, continuando", exc_info=True)
        await trace_interaction("JUDGE", msg, {"n_itens": len(items), "status": "ERROR"})
        await trace_flow("EXIT", "node.judge", msg, {"status": "ERROR", "fallback": True})
    await trace_interaction("NOC", msg, {"node": "judge", "protocolo": protocolo_id})
    return {**state, "protocolo_id": protocolo_id}


# ---------------------------------------------------------------------------
# Roteamento condicional
# ---------------------------------------------------------------------------

def _after_guardrails(state: GraphState) -> str:
    return END if state["blocked"] else "routing_decision"


def _after_routing(state: GraphState) -> str:
    route = state.get("route", "supervisor_agent")
    _map = {
        "informacao_agent":    "informacao",
        "cancelamento_agent":  "cancelamento_retencao",
        "ativacao_agent":      "ativacao",
        "mudanca_plano_agent": "mudanca_plano",
        "supervisor_agent":    "supervisor",
    }
    return _map.get(route, "supervisor")


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Monta a topologia do StateGraph com 9 nós e 3 arestas condicionais."""
    g = StateGraph(GraphState)

    g.add_node("input_guardrails",      node_input_guardrails)
    g.add_node("routing_decision",      node_routing_decision)
    g.add_node("informacao",            node_informacao)
    g.add_node("cancelamento_retencao", node_cancelamento_retencao)
    g.add_node("ativacao",              node_ativacao)
    g.add_node("mudanca_plano",         node_mudanca_plano)
    g.add_node("supervisor",            node_supervisor)
    g.add_node("output_guardrails",     node_output_guardrails)
    g.add_node("judge",                 node_judge)

    g.set_entry_point("input_guardrails")
    g.add_conditional_edges("input_guardrails", _after_guardrails)
    g.add_conditional_edges(
        "routing_decision",
        _after_routing,
        {
            "informacao":            "informacao",
            "cancelamento_retencao": "cancelamento_retencao",
            "ativacao":              "ativacao",
            "mudanca_plano":         "mudanca_plano",
            "supervisor":            "supervisor",
        },
    )
    for node in ["informacao", "cancelamento_retencao", "ativacao", "mudanca_plano", "supervisor"]:
        g.add_edge(node, "output_guardrails")
    g.add_edge("output_guardrails", "judge")
    g.add_edge("judge", END)

    return g


_compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Serialização de estado (eventos STATE / GRAPH / ORCH)
# ---------------------------------------------------------------------------

def _serialize_guardrail(r: Any) -> dict:
    action_str = str(getattr(r, "action_taken", "")).lower()
    return {
        "type": getattr(r, "guardrail_type", "?"),
        "violation": getattr(getattr(r, "violation", None), "value", "?"),
        "blocked": "block" in action_str,
    }


def _state_snapshot(state: dict, include_empty: bool = False) -> dict:
    result = {}
    for k in ("sanitized_input", "route", "intent", "answer", "final_answer", "blocked", "chunk_id"):
        v = state.get(k)
        if not include_empty and (v is None or v == "" or v is False):
            continue
        result[k] = (v[:120] + "…") if isinstance(v, str) and len(v) > 120 else v
    decisions = state.get("guardrail_decisions") or []
    if include_empty or decisions:
        result["guardrail_decisions"] = [_serialize_guardrail(r) for r in decisions]
    return result


def _state_delta(prev: dict, current: dict) -> dict:
    changed = {}
    for k, curr_v in current.items():
        if k == "channel_message":
            continue
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
    handoff_origem: str | None = None,
) -> str:
    """Executa o grafo completo para uma mensagem e retorna a resposta final."""
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
        handoff_origem=handoff_origem,
        protocolo_id=None,
    )

    await trace_interaction("GRAPH", channel_message, {
        "graph_nodes": 9,
        "entry_point": "input_guardrails",
        "compiled": True,
        "initial_state": _state_snapshot(initial_state, include_empty=True),
    })

    t_inicio = time.perf_counter()
    current: dict = dict(initial_state)
    async for chunk in _compiled_graph.astream(initial_state, config=config or {}, stream_mode="updates"):
        for node_name, node_delta in chunk.items():
            if node_name.startswith("__"):
                continue
            prev = dict(current)
            current.update(node_delta)
            delta = _state_delta(prev, current)
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
        "chunk_id": final_state.get("chunk_id"),
        "protocolo_id": final_state.get("protocolo_id"),
        "guardrails_triggered": len(final_state.get("guardrail_decisions") or []),
        "final_state": _state_snapshot(final_state),
    })

    if final_state.get("blocked"):
        return (
            "Não consigo continuar o atendimento. "
            "Por favor, reformule sua mensagem para que eu possa te ajudar."
        )

    return final_state.get("final_answer") or final_state.get("answer") or ""


# ---------------------------------------------------------------------------
# Helpers de negócio
# ---------------------------------------------------------------------------

async def _run_catalog(text: str, msg: ChannelMessage) -> tuple[str, str | None]:
    """Consulta o catálogo RAG e chama o LLM com o contexto encontrado."""
    try:
        from agent.prompt import build_not_found_prompt, build_prompt, build_system_prompt, not_found_response
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
            prompt = build_not_found_prompt(text)
            response = await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
            return response, None

        await trace_flow("ENTER", "prompt.build", msg)
        prompt = build_prompt(text, result)
        await trace_flow("EXIT", "prompt.build", msg, {"status": "OK"})

        if prompt is None:
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


async def _run_subcaso_cobranca(text: str, msg: ChannelMessage) -> str:
    """Subcaso cobrança dentro da jornada de Informação (Escopo v1.2 § 3.1).

    Consulta TIM/Clientes (CRM) primeiro para identificar contrato e segmento
    do cliente antes de responder à dúvida de cobrança ou emitir segunda via.
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
        nome = cliente.get("nome", "cliente")
        segmento = cliente.get("segmento", "padrão")
        plano = cliente.get("plano_atual", "seu plano")
        mensalidade = cliente.get("mensalidade", 0)
        pede_segunda_via = any(
            kw in text.lower()
            for kw in ("segunda via", "boleto", "pagar", "pagamento")
        )
        if pede_segunda_via:
            return (
                f"Olá, {nome}! Identifiquei seu contrato {segmento}: {plano}. "
                f"Sua fatura é de R${mensalidade:.2f}. "
                "Posso enviar a segunda via por e-mail ou SMS. Qual prefere?"
            )
        from agent.prompt import build_crm_prompt, build_system_prompt
        prompt = build_crm_prompt(text, "billing", cliente)
        return await _call_llm_and_trace(prompt, msg, system=build_system_prompt())
    except Exception:
        logger.warning("subcaso_cobranca falhou", exc_info=True)
        return "Não consegui acessar as informações de fatura no momento."


async def _acionar_ath(msg: ChannelMessage, motivo: str) -> None:
    """CAN-05: dispara transbordo para Atendimento Humano (ATH) em exceção negocial."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{MOCK_BASE}/ath/transbordo",
                json={"conversation_id": msg.session_id, "motivo": motivo, "canal": "digital"},
            )
    except Exception:
        logger.warning("ath_transbordo falhou", exc_info=True)


async def _run_cancelamento_retencao(text: str, msg: ChannelMessage) -> str:
    """Jornada de Cancelamento: Retenção/Reversão + ATH (Escopo v1.2 § 3.4).

    CAN-01: GET /catalogo/retencao/{cpf} — ofertas de retenção do cliente.
    CAN-02: apresenta contra-oferta de retenção antes do cancelamento definitivo.
    CAN-03: GET /catalogo/reversao/{cpf} — quando cliente já cancelou e quer reverter.
    CAN-04: isencao_multa incluída na oferta vinda do catálogo quando elegível.
    CAN-05: POST /ath/transbordo — apenas se não houver ofertas disponíveis.
    """
    try:
        await trace_flow("ENTER", "mock.crm", msg, {"endpoint": f"/crm/cliente/{MOCK_CPF}"})
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            cliente = r_crm.json()
        latencia_ms = int((time.perf_counter() - t0) * 1000)
        await trace_flow("EXIT", "mock.crm", msg, {
            "status": "OK", "http_status": r_crm.status_code, "latencia_ms": latencia_ms,
        })
        await trace_interaction("MOCK", msg, {
            "service": "crm", "endpoint": f"/crm/cliente/{MOCK_CPF}",
            "http_status": r_crm.status_code, "latencia_ms": latencia_ms, "owner": "KIRLLEN",
        })
        nome = cliente.get("nome", "cliente")
        plano = cliente.get("plano_atual", "seu plano")
        segmento = cliente.get("segmento", "padrão")

        # CAN-03: detectar solicitação de reversão (cliente já cancelou e quer voltar)
        pede_reversao = any(
            kw in text.lower()
            for kw in ("reverter", "desfazer", "mudei de ideia", "não quero mais cancelar", "voltei atrás")
        )
        if pede_reversao:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r_rev = await client.get(f"{MOCK_BASE}/catalogo/reversao/{MOCK_CPF}")
                reversao = r_rev.json()
            oferta = reversao.get("oferta_reversao", {})
            msg_isencao = " Com isenção total de multa." if reversao.get("isencao_multa") else ""
            return (
                f"Olá, {nome}! Ficamos felizes em saber que reconsiderou. "
                f"Podemos reverter o cancelamento do seu {plano}.{msg_isencao} "
                f"Benefício: {oferta.get('descricao', 'manutenção do seu plano')}. "
                "Confirma a reversão?"
            )

        # CAN-01: Catálogo de Retenção
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_ret = await client.get(f"{MOCK_BASE}/catalogo/retencao/{MOCK_CPF}")
            retencao = r_ret.json()

        ofertas = retencao.get("ofertas", [])
        if not ofertas:
            # CAN-05: sem ofertas → transbordo para ATH
            await _acionar_ath(msg, motivo="sem_oferta_retencao")
            return (
                f"Olá, {nome}! Lamentamos sua decisão de cancelar o {plano}. "
                "Vou conectá-lo com um especialista que pode oferecer condições exclusivas. "
                "Aguarde um momento."
            )

        # CAN-02: apresentar melhor contra-oferta + CAN-04: isenção de multa
        melhor = ofertas[0]
        msg_isencao = " Sem cobrança de multa." if retencao.get("isencao_multa") else ""
        return (
            f"Olá, {nome}! Entendemos que deseja cancelar o {plano} (segmento {segmento}). "
            f"Antes de finalizar, temos uma oferta exclusiva para você: "
            f"{melhor['descricao']}.{msg_isencao} "
            "Gostaria de aproveitar essa condição?"
        )
    except Exception:
        logger.warning("cancelamento_retencao falhou", exc_info=True)
        return "Não consegui processar sua solicitação de cancelamento no momento. Tente novamente."


async def _run_ativacao(text: str, msg: ChannelMessage) -> str:
    """Jornada de Ativação: Crivo/Score → Catálogo Pré → apresentação da oferta (Escopo v1.2 § 3.2).

    Sem handoff externo: elegibilidade e oferta são resolvidas diretamente nesta jornada.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_score = await client.get(f"{MOCK_BASE}/crivo/score/{MOCK_CPF}")
            score = r_score.json()

        if not score.get("elegivel"):
            motivo = score.get("motivo", "critérios de crédito não atendidos")
            return (
                f"Infelizmente a ativação para Controle não está disponível agora. "
                f"Motivo: {motivo}. Posso ajudar com mais alguma coisa?"
            )

        async with httpx.AsyncClient(timeout=5.0) as client:
            r_catalogo = await client.get(f"{MOCK_BASE}/catalogo/pre")
            catalogo = r_catalogo.json()

        ofertas = catalogo.get("ofertas", [])
        if not ofertas:
            return "Não encontrei ofertas de ativação disponíveis no momento. Tente novamente mais tarde."

        linhas = [
            f"  • {o['nome']}: R${o['preco']:.2f}/mês — {o.get('descricao', '')}"
            for o in ofertas
        ]
        return (
            "Ótima notícia! Você está elegível para migrar para o Controle. "
            "Veja as opções disponíveis:\n"
            + "\n".join(linhas)
            + "\n\nQual dessas ofertas você gostaria de ativar?"
        )
    except Exception:
        logger.warning("ativacao falhou", exc_info=True)
        return "Não consegui acessar as ofertas de ativação no momento. Tente novamente."


async def _run_mudanca_plano(text: str, msg: ChannelMessage, handoff_origem: str | None) -> str:
    """Jornada de Mudança de Plano: Elegibilidade → Simulação (Escopo v1.2 § 3.3).

    Etapa 1 — Elegibilidade Completa: verifica se o cliente pode trocar de plano.
               Pulada quando handoff_origem == "agente_contas" (Subfluxo Contas).
    Etapa 2 — Simulação direta se plano-alvo detectado na mensagem; caso contrário,
               lista as opções disponíveis (Catálogo NBA para up, Retenção para down).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            r_eleg = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
            cliente = r_crm.json()
            elegibilidade = r_eleg.json()

        nome = cliente.get("nome", "cliente")

        # Etapa 1: verificação de elegibilidade — pulada no Subfluxo Contas
        if handoff_origem != "agente_contas" and not elegibilidade.get("pode_trocar"):
            return f"Olá, {nome}! No momento não é possível realizar a troca de plano."

        # Etapa 2: plano-alvo identificado na mensagem → simular diretamente
        plano_alvo = _extrair_plano(text)
        if plano_alvo:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r_sim = await client.post(
                    f"{MOCK_BASE}/planos/simular-troca",
                    json={"cpf": MOCK_CPF, "plano_destino": plano_alvo},
                )
                data = r_sim.json()
            if "erro" in data:
                return f"Não consegui simular a troca: {data['erro']}"
            sinal = "+" if data["diferenca_mensal"] >= 0 else ""
            multa = (
                f" Multa de fidelidade: R${data['multa_se_aplicavel']:.2f}."
                if data.get("multa_se_aplicavel", 0) > 0
                else ""
            )
            aviso_fidelidade = ""
            if elegibilidade.get("fidelidade_ativa") and handoff_origem != "agente_contas":
                aviso_fidelidade = (
                    f" Fidelidade ativa até {_fmt_data(elegibilidade.get('fim_fidelidade'))}."
                )
            return (
                f"Olá, {nome}! Simulação: {data['plano_atual']} → {data['plano_destino']}. "
                f"Atual: R${data['mensalidade_atual']:.2f} | Nova: R${data['mensalidade_destino']:.2f} "
                f"({sinal}R${data['diferenca_mensal']:.2f}/mês).{multa}{aviso_fidelidade} "
                f"Vigência: {_fmt_data(data['data_vigencia'])}. Confirma a troca?"
            )

        # Etapa 2 (sem plano-alvo): listar opções disponíveis
        planos_disp = elegibilidade.get("planos_disponiveis", [])
        planos_fmt = ", ".join(planos_disp) if planos_disp else "nenhum disponível"
        aviso_fidelidade = ""
        if elegibilidade.get("fidelidade_ativa"):
            aviso_fidelidade = (
                f" Você está em fidelidade até {_fmt_data(elegibilidade.get('fim_fidelidade'))} "
                f"(multa: R${elegibilidade.get('multa_cancelamento', 0):.2f})."
            )
        return (
            f"Olá, {nome}! Você pode trocar de plano.{aviso_fidelidade} "
            f"Planos disponíveis: {planos_fmt}. "
            "Qual plano você gostaria de simular?"
        )
    except Exception:
        logger.warning("mudanca_plano falhou", exc_info=True)
        return "Não consegui processar sua solicitação de mudança de plano no momento."


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

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


def _fmt_data(iso: str | None) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/YYYY'."""
    if not iso:
        return iso or ""
    try:
        from datetime import date
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _extrair_plano(texto: str) -> str | None:
    """Extrai o identificador canônico do plano destino a partir do texto livre."""
    texto = texto.lower()
    for alias, plano_id in _PLANO_ALIAS.items():
        if alias in texto:
            return plano_id
    return None
