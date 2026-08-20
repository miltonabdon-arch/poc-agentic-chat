"""Publisher Langfuse v2 via REST API (/api/public/ingestion).

O SDK langfuse>=4.x usa OpenTelemetry OTLP, incompatível com o servidor
langfuse/langfuse:2. Este publisher implementa AnalyticsPublisher usando
httpx para chamar o endpoint REST que o servidor v2 expõe.

SOLID — Dependency Inversion:
  AgentObserver depende do contrato AnalyticsPublisher (abstração).
  LangfuseRestPublisher é a implementação concreta injetada em tracer.py.
  A cadeia framework permanece intacta:
    tracer → AgentObserver → LangfuseRestPublisher → POST /api/public/ingestion

Responsabilidade: AI Developer Sr (Igor Scaglia)
"""
import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from agent_framework.analytics import AnalyticsPublisher

logger = logging.getLogger(__name__)


class LangfuseRestPublisher(AnalyticsPublisher):
    """Publica eventos IC/NOC/GRL/etc. no Langfuse v2 via REST.

    Estrutura Langfuse:
      sessionId = session_id do ChannelMessage (conversa — persiste entre turnos)
      traceId   = UUID novo por IC (turno) — distingue cada interação na sessão

    Compatível com servidor langfuse/langfuse:2 sem dependência de OTel.
    """

    def __init__(self) -> None:
        self.enabled = False
        self._host = ""
        self._auth = ""
        # Mapeia session_id → trace_id do turno corrente
        self._active_traces: dict[str, str] = {}

        pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
        host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")

        if not pk or not sk:
            return

        self._host = host.rstrip("/")
        token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
        self._auth = f"Basic {token}"
        self.enabled = True
        logger.info("LangfuseRestPublisher ativo host=%s", self._host)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return

        # payload é o envelope gerado por build_analytics_event()
        body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        event_date = payload.get("eventDate") or datetime.now(timezone.utc).isoformat()

        session_id = str(body.get("session_id") or "")
        if not session_id:
            return

        batch: list[dict[str, Any]] = []

        # IC → início de novo turno: gera trace_id único para este turno
        if event_type == "IC":
            trace_id = str(uuid4())
            self._active_traces[session_id] = trace_id
            batch.append({
                "id": str(uuid4()),
                "type": "trace-create",
                "timestamp": event_date,
                "body": {
                    "id": trace_id,
                    "name": "poc-agente-tim",
                    "sessionId": session_id,  # agrupa todos os turnos na mesma sessão
                    "input": {"text": body.get("text", ""), "canal": body.get("canal", "")},
                    "metadata": {"session_id": session_id, "canal": body.get("canal", "")},
                },
            })
        else:
            # Reutiliza o trace_id do turno corrente; fallback para session_id se IC ainda não chegou
            trace_id = self._active_traces.get(session_id, session_id)

        # Um span por evento — associado ao trace do turno corrente
        batch.append({
            "id": str(uuid4()),
            "type": "span-create",
            "timestamp": event_date,
            "body": {
                "id": str(uuid4()),
                "traceId": trace_id,
                "name": str(event_type),
                "startTime": event_date,
                "endTime": event_date,
                "input": {k: str(v) for k, v in body.items()},
                "metadata": {
                    "source": payload.get("source", "agent_framework"),
                    "event_type": event_type,
                },
            },
        })

        await self._ingest(batch, event_type, trace_id)

    async def _ingest(self, batch: list[dict[str, Any]], event_type: str, trace_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{self._host}/api/public/ingestion",
                    json={"batch": batch},
                    headers={
                        "Authorization": self._auth,
                        "Content-Type": "application/json",
                    },
                )
            if r.status_code >= 400:
                logger.warning(
                    "LangfuseRest ingestão falhou event_type=%s status=%d: %s",
                    event_type, r.status_code, r.text[:300],
                )
            else:
                logger.debug(
                    "LangfuseRest OK event_type=%s trace_id=%s status=%d",
                    event_type, trace_id, r.status_code,
                )
        except Exception:
            logger.debug("LangfuseRest publish erro event_type=%s", event_type, exc_info=True)
