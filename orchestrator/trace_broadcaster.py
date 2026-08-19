"""Broadcaster de eventos de trace para consumidores async (Chainlit, SSE).

AI Developer Sr — Igor Scaglia

Desacopla a camada de observabilidade (tracer.py) dos consumidores que precisam
reagir a eventos em tempo real (Chainlit TaskList, HTML diagram SSE).

Padrão publish/subscribe por asyncio.Queue: cada subscriber recebe uma cópia
independente dos eventos. Adequado para a PoC (volume baixo; sem backpressure).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class TraceBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    async def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                await q.put(event)
            except Exception:
                logger.warning("TraceBroadcaster: falha ao publicar evento", exc_info=True)


_broadcaster = TraceBroadcaster()


def get_broadcaster() -> TraceBroadcaster:
    return _broadcaster
