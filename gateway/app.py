"""Runtime FastAPI — wrapper do orquestrador LangGraph.

Expõe:
  POST /agent/interact  — normaliza entrada e chama run_interaction()
  GET  /trace           — SSE stream de eventos em tempo real (broadcaster)
  GET  /chainlit/*      — redireciona para o servidor Chainlit standalone (:8080)
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

CHAINLIT_URL = os.getenv("CHAINLIT_URL", "http://localhost:8080")

load_dotenv()

from gateway.channel_gateway import normalize  # noqa: E402
from gateway.health import report_health  # noqa: E402
from orchestrator.graph import run_interaction  # noqa: E402

app = FastAPI(title="PoC Agente de Catálogo TIM")

STATIC_DIR = Path(__file__).parent / "static"


class InteractRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class InteractResponse(BaseModel):
    conversation_id: str
    response: str


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
    channel_message = normalize(request.message, request.conversation_id)
    response_text = await run_interaction(channel_message)
    return InteractResponse(
        conversation_id=channel_message.session_id,
        response=response_text,
    )


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


