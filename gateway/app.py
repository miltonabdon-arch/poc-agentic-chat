"""Runtime FastAPI — wrapper do orquestrador LangGraph.

Expõe:
  POST /agent/interact        — normaliza entrada e chama run_interaction()
  GET  /trace                 — SSE stream de eventos em tempo real (broadcaster)
  GET  /chainlit/*            — redireciona para o servidor Chainlit standalone (:8080)
  POST /agent/sse             — canal URA: resposta em texto simples sem markdown
  GET  /agent/sse             — SSE para URA: emite apenas o evento SUMARIO final
  POST /agent/handoff/receber — recebe handoff de outro agente com contexto pré-carregado
"""

import asyncio
import json
import os
import re as _re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

CHAINLIT_URL = os.getenv("CHAINLIT_URL", "http://localhost:8080")

load_dotenv()

from gateway.channel_gateway import normalize  # noqa: E402
from gateway.health import report_health  # noqa: E402
from gateway.models import HandoffPayload  # noqa: E402
from orchestrator.graph import run_interaction  # noqa: E402

app = FastAPI(title="PoC Agente de Catálogo TIM")


@app.on_event("startup")
async def _preload_models():
    import asyncio
    import logging

    async def _bg():
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _load_reranker)
        except Exception as exc:
            logging.getLogger(__name__).warning("Re-ranker não pré-carregado: %s", exc)

    asyncio.create_task(_bg())


def _load_reranker():
    from rag_pipeline.query_api import _get_reranker
    _get_reranker()

STATIC_DIR = Path(__file__).parent / "static"


def _strip_markdown(text: str) -> str:
    """Remove formatação markdown para canal de voz — asteriscos e cabeçalhos não podem ser lidos."""
    text = _re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    text = _re.sub(r"^#{1,6}\s+", "", text, flags=_re.MULTILINE)
    text = _re.sub(r"^\s*[-*+]\s+", "", text, flags=_re.MULTILINE)
    text = _re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = _re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    return text.strip()


class InteractRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class InteractResponse(BaseModel):
    conversation_id: str
    response: str


class SSERequest(BaseModel):
    message: str
    conversation_id: str | None = None


@app.get("/chainlit")
@app.get("/chainlit/{path:path}")
async def chainlit_redirect(path: str = ""):
    return RedirectResponse(url=CHAINLIT_URL, status_code=302)


@app.get("/health")
def health():
    return report_health()


@app.get("/chat")
def chat_ui():
    """Chat HTML mínimo para validação manual — não é frontend de produção,
    ver docs/CRITERIOS-DE-ACEITE.md para o checklist formal de demo."""
    return FileResponse(STATIC_DIR / "chat.html")


@app.post("/agent/interact", response_model=InteractResponse)
async def interact(request: InteractRequest):
    channel_message = await normalize(request.message, request.conversation_id)
    response_text = await run_interaction(channel_message)
    return InteractResponse(
        conversation_id=channel_message.session_id,
        response=response_text,
    )


@app.post("/agent/sse")
async def sse_interact(request: SSERequest):
    """Canal URA/voz — resposta em texto simples, markdown removido incondicionalmente."""
    channel_message = await normalize(request.message, request.conversation_id, canal="voice")
    response_text = await run_interaction(channel_message)
    return {
        "conversation_id": channel_message.session_id,
        "response": _strip_markdown(response_text),
    }


@app.get("/agent/sse")
async def sse_stream_ura():
    """SSE para URA — emite apenas o evento SUMARIO (resposta final do pipeline)."""
    from orchestrator.trace_broadcaster import get_broadcaster

    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"keepalive\"}\n\n"
                    continue
                if event.get("type") == "SUMARIO":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    break
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/agent/handoff/receber")
async def handoff_receber(payload: HandoffPayload):
    """Recebe handoff de outro agente e retoma a conversa com contexto pré-carregado.

    O campo `origem_agente` é propagado ao grafo como `handoff_origem`.
    Quando `origem_agente == "agente_contas"`, a jornada de Mudança de Plano
    pula a verificação de elegibilidade (Subfluxo Contas — Escopo v1.2 § 3.3).
    """
    channel_message = await normalize(
        payload.intencao_sugerida,
        payload.conversation_id,
    )
    response_text = await run_interaction(
        channel_message,
        handoff_origem=payload.origem_agente,
    )
    return {
        "conversation_id": channel_message.session_id,
        "response": response_text,
        "protocolo_recebido": payload.protocolo,
        "origem_agente": payload.origem_agente,
    }


@app.get("/trace")
async def trace_stream():
    """SSE stream de eventos do pipeline — aberto para qualquer cliente (Chainlit, curl, browser)."""
    from orchestrator.trace_broadcaster import get_broadcaster

    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"keepalive\"}\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


