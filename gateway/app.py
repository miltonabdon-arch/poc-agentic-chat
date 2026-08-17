"""Runtime FastAPI — wrapper do orquestrador LangGraph.

Expõe POST /agent/interact delegando para orchestrator.graph.run_interaction().
run_interaction é async; FastAPI suporta endpoints async nativamente.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from gateway.channel_gateway import normalize
from gateway.health import report_health
from orchestrator.graph import run_interaction

app = FastAPI(title="PoC Agente de Catálogo TIM")

STATIC_DIR = Path(__file__).parent / "static"


class InteractRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class InteractResponse(BaseModel):
    conversation_id: str
    response: str


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
