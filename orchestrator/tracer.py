"""Observability tracer — wrapper sobre AgentObserver do agent_framework.

Sem credenciais OCI configuradas, AgentObserver opera em modo silent
(analytics=None, event_bus=None): emite apenas logs locais via logging.
Isso é suficiente para a PoC local; no projeto real, o publisher OCI
é injetado via DI.
"""

import logging

from agent_framework.channels.base import ChannelMessage
from agent_framework.observability.observer import AgentObserver

logger = logging.getLogger(__name__)

_observer = AgentObserver(analytics=None, event_bus=None)


async def trace_interaction(
    event_type: str,
    channel_message: ChannelMessage,
    payload: dict | None = None,
) -> None:
    """Emite um evento de observabilidade.

    event_type: "IC" (interaction created), "NOC" (node completed),
                "GRL" (guardrail).
    """
    try:
        await _observer.emit(
            event_type=event_type,
            payload={
                "session_id": channel_message.session_id,
                "channel": channel_message.channel,
                **(payload or {}),
            },
        )
    except Exception:
        logger.warning("tracer emit falhou (modo silent)", exc_info=True)
