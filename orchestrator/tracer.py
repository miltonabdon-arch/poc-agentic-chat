"""Observabilidade — wrapper sobre AgentObserver do agent_framework.

Responsabilidade: AI Developer Sr (Igor Scaglia)

Quatro camadas de emissão, conforme CRITERIOS-DE-ACEITE §6:

  1. AgentObserver (agent_framework — SPEC-007-lite):
     Emite eventos IC/NOC/GRL para o barramento do framework. Em ambiente
     local opera em modo noop (analytics=None). No projeto real, o publisher
     OCI é injetado via DI sem alterar este contrato.

  2. Log estruturado local (expansão sobre o framework):
     Para atender §6 (latência + guardrail acionado + chunk_id visíveis no
     log), adicionamos log explícito via logging padrão.

  3. TraceBroadcaster → SSE / Chainlit:
     Pub/sub asyncio.Queue — cada GET /trace recebe fila independente.

  4. Langfuse (quando LANGFUSE_PUBLIC_KEY configurado):
     Injetado como analytics= no AgentObserver. Eventos IC/NOC/GRL vão
     automaticamente; FLOW/LLM/RAG/MOCK/JUDGE/GRAPH/ORCH/STATE publicam via
     broadcaster e são visíveis no log local.
"""

import logging
import os

from agent_framework.channels.base import ChannelMessage
from agent_framework.observability.observer import AgentObserver
from orchestrator.trace_broadcaster import get_broadcaster

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapeamento componente → responsável (rastreabilidade nos logs do terminal)
# ---------------------------------------------------------------------------

NODE_OWNERS: dict[str, str] = {
    # Nós LangGraph — Igor Scaglia (AI Developer Sr)
    "node.input_guardrails": "IGOR",
    "node.routing_decision": "IGOR",
    "node.catalog_agent": "IGOR",
    "node.billing": "IGOR",
    "node.handoff_cancellation": "IGOR",
    "node.handoff_deals": "IGOR",
    "node.eligibility": "IGOR",
    "node.simulation": "IGOR",
    "node.supervisor": "IGOR",
    "node.output_guardrails": "IGOR",
    "node.judge": "IGOR",
    # RAG pipeline — Ana Carolina Bergamasco
    "rag.query": "ANA",
    "rag.vectorizer": "ANA",
    # Agent / prompts / guardrails / judge — Gustavo Bezerra
    "llm.complete": "GUSTAVO",
    "prompt.build": "GUSTAVO",
    "guardrail.input": "GUSTAVO",
    "guardrail.output": "GUSTAVO",
    "judge.batch": "GUSTAVO",
    # Mock services / Gateway — Kirllen Silva
    "mock.crm": "KIRLLEN",
    "mock.elegibilidade": "KIRLLEN",
    "mock.cancellation": "KIRLLEN",
    "mock.deals": "KIRLLEN",
    "mock.simular_troca": "KIRLLEN",
    "gateway.normalize": "KIRLLEN",
}

# ---------------------------------------------------------------------------
# Camada 4: Langfuse v2 via REST (compatível com langfuse/langfuse:2)
# LangfuseRestPublisher implementa AnalyticsPublisher e é injetado no
# AgentObserver — cadeia framework intacta (Dependency Inversion / SOLID).
# ---------------------------------------------------------------------------

_langfuse_publisher = None
if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
    try:
        from orchestrator.langfuse_rest_publisher import LangfuseRestPublisher
        _langfuse_publisher = LangfuseRestPublisher()
    except Exception:
        logger.warning("LangfuseRestPublisher indisponível", exc_info=True)

# Camada 1: AgentObserver com publisher REST injetado quando disponível
_observer = AgentObserver(analytics=_langfuse_publisher, event_bus=None)


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

async def trace_interaction(
    event_type: str,
    channel_message: ChannelMessage,
    payload: dict | None = None,
) -> None:
    """Emite evento de interação para as 3 camadas de observabilidade.

    Tipos suportados:
      - IC    : Interaction Created (início de sessão)
      - NOC   : Node Completed (nó do grafo concluído)
      - GRL   : GuaRaiL acionado (input ou output)
      - GRAPH : topologia do grafo compilado + estado inicial
      - ORCH  : orquestração concluída + estado final
      - LLM   : chamada ao modelo de linguagem
      - RAG   : busca no catálogo vetorial
      - MOCK  : chamada HTTP a mock_services
      - JUDGE : avaliação offline de qualidade
      - STATE : snapshot do GraphState após cada nó (demo/narrativa local)

    Camada 1 (AgentObserver/Langfuse): recebe todos os tipos exceto STATE.
    STATE é evento de narrativa de demo — log local + broadcaster apenas.
    Camadas 2 e 3 (log + broadcaster): recebem todos os tipos sem exceção.
    """
    dados = {
        "session_id": channel_message.session_id,
        "canal": channel_message.channel,
        **(payload or {}),
    }

    # Camada 1: AgentObserver → Langfuse (IC/NOC/GRL recebem tratamento completo;
    # outros tipos passam como eventos genéricos, suficiente para a PoC).
    # STATE é excluído pois é artefato de demo sem valor semântico de produção.
    if event_type != "STATE":
        try:
            await _observer.emit(event_type=event_type, payload=dados)
        except Exception:
            logger.warning("AgentObserver emit falhou (modo noop)", exc_info=True)

    # Camada 2: log local legível — atende §6 sem depender do publisher OCI
    _log_evento_local(event_type, dados)

    # Camada 3: broadcaster → SSE / Chainlit
    await get_broadcaster().publish({"type": event_type, **dados})


async def trace_flow(
    subtype: str,
    component: str,
    channel_message: ChannelMessage,
    payload: dict | None = None,
) -> None:
    """Emite evento FLOW ENTER ou EXIT para visibilidade em tempo real.

    subtype   : "ENTER" imediatamente antes do componente iniciar;
                "EXIT" imediatamente após completar (ou falhar).
    component : chave de NODE_OWNERS (ex.: "node.catalog_agent", "llm.complete").

    ENTER → abre step expansível no Chainlit antes de qualquer latência.
    EXIT  → fecha step com status e latência medida.

    FLOW não passa pelo AgentObserver (é extensão local da PoC),
    apenas camadas 2 (log) e 3 (broadcaster SSE).
    """
    owner = NODE_OWNERS.get(component, "IGOR")
    dados = {
        "session_id": channel_message.session_id,
        "canal": channel_message.channel,
        "subtype": subtype,
        "component": component,
        "owner": owner,
        **(payload or {}),
    }

    # Camada 2 + 3 apenas: FLOW é extensão local, não passa pelo AgentObserver
    _log_evento_local("FLOW", dados)
    await get_broadcaster().publish({"type": "FLOW", **dados})


def _log_evento_local(event_type: str, dados: dict) -> None:
    """Formata evento como linha de log estruturada legível por humanos.

    Formato 'TRACE|tipo|chave=valor|...' para grep fácil no terminal (§6).
    Inclui apenas as chaves presentes no payload — campos ausentes são omitidos.
    """
    partes = [f"TRACE|{event_type}"]
    for chave in (
        "session_id", "canal",
        # Identidade do nó ou componente
        "node", "component", "subtype", "owner",
        # Guardrail
        "guardrail", "violation", "blocked",
        # Roteamento
        "intent", "agent",
        # RAG
        "chunk_id", "found", "score",
        # LLM
        "model", "tokens", "prompt_len", "response_len",
        # Mock services
        "service", "endpoint", "http_status",
        # Judge
        "n_itens",
        # Genérico
        "latencia_ms", "status", "fallback",
    ):
        if chave in dados:
            partes.append(f"{chave}={dados[chave]}")
    logger.info(" | ".join(partes))


def log_sumario_interacao(
    channel_message: ChannelMessage,
    latencia_ms: int,
    chunk_id: str | None,
    guardrail_decisions: list,
) -> None:
    """Registra o sumário completo da interação ao final do fluxo.

    Agrega latência total, chunk usado e todos os guardrails acionados
    numa única linha de log, conforme CRITERIOS-DE-ACEITE §6.
    Filtra apenas violações reais (Violation.NONE é omitido).
    """
    from agent.models import Violation
    # Inclui apenas guardrails que registraram uma violação efetiva
    guardrails_acionados = [
        f"{r.guardrail_type}:{r.violation.value}"
        for r in guardrail_decisions
        if hasattr(r, "violation") and r.violation != Violation.NONE
    ]

    logger.info(
        "TRACE|SUMARIO | session_id=%s | canal=%s | latencia_ms=%d"
        " | chunk_id=%s | guardrails_acionados=%s",
        channel_message.session_id,
        channel_message.channel,
        latencia_ms,
        chunk_id or "nenhum",
        guardrails_acionados or "nenhum",
    )
