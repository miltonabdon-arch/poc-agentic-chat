"""Observabilidade — wrapper sobre AgentObserver do agent_framework.

Responsabilidade: AI Developer Sr (Igor Scaglia)

Duas camadas de emissão, conforme CRITERIOS-DE-ACEITE §6:

  1. AgentObserver (agent_framework — SPEC-007-lite):
     Emite eventos IC/NOC/GRL para o barramento do framework. Em ambiente
     local opera em modo noop (analytics=None). No projeto real, o publisher
     OCI é injetado via DI sem alterar este contrato.

  2. Log estruturado local (expansão sobre o framework):
     O AgentObserver noop não imprime o payload — apenas confirma a emissão.
     Para atender §6 (latência + guardrail acionado + chunk_id visíveis no
     log), adicionamos log explícito via logging padrão. Esta camada NÃO
     existe no framework real — é uma adição da PoC para rastreabilidade local.
"""

import logging

from agent_framework.channels.base import ChannelMessage
from agent_framework.observability.observer import AgentObserver
from orchestrator.trace_broadcaster import get_broadcaster

logger = logging.getLogger(__name__)

# Expansão sobre SPEC-007: AgentObserver em modo noop (sem OCI publisher).
# No projeto real, 'analytics' recebe o publisher OCI e 'event_bus' o barramento
# de eventos interno — ambos injetados via DI pelo AgentRuntimeMixin.
_observer = AgentObserver(analytics=None, event_bus=None)


async def trace_interaction(
    event_type: str,
    channel_message: ChannelMessage,
    payload: dict | None = None,
) -> None:
    """Emite um evento de observabilidade nas duas camadas.

    event_type:
      "IC"  — Interaction Created (início da sessão)
      "NOC" — Node Completed (nó do grafo LangGraph concluído)
      "GRL" — Guardrail (guardrail de input ou output acionado)

    Conforme CRITERIOS-DE-ACEITE §6: guardrails acionados e chunk_id
    ficam visíveis no log local mesmo quando o AgentObserver opera em noop.
    """
    dados = {
        "session_id": channel_message.session_id,
        "canal": channel_message.channel,
        **(payload or {}),
    }

    # Camada 1: framework (noop local, real em OCI)
    try:
        await _observer.emit(event_type=event_type, payload=dados)
    except Exception:
        logger.warning("AgentObserver emit falhou (modo noop)", exc_info=True)

    # Camada 2: log local legível — atende §6 sem depender do publisher OCI
    _log_evento_local(event_type, dados)

    # Camada 3: broadcaster para Chainlit TaskList e SSE do diagrama HTML
    await get_broadcaster().publish({"type": event_type, **dados})


def _log_evento_local(event_type: str, dados: dict) -> None:
    """Formata o evento como linha de log estruturada legível por humanos.

    Decisão: formato 'TRACE|tipo|chave=valor|...' em vez de JSON puro para
    facilitar grep no terminal durante a demo (§6 exige verificabilidade visual).
    """
    partes = [f"TRACE|{event_type}"]
    for chave in ("session_id", "canal", "node", "guardrail", "violation",
                  "blocked", "intent", "agent", "chunk_id", "latencia_ms"):
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

    Chamado por run_interaction() após o grafo completar — agrega latência
    total, chunk usado e todos os guardrails acionados numa única linha de log,
    conforme exigido por CRITERIOS-DE-ACEITE §6.
    """
    # Decisão: guardrail_decisions vem do GraphState (lista de GuardrailResult).
    # Filtramos apenas as violações não-NONE para o sumário ser signal/noise alto.
    from agent.models import Violation
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
