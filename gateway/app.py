"""Runtime FastAPI - expoe POST /agent/interact, delegando para o
orquestrador (orchestrator/graph.py). Não usa AgentRuntimeMixin real do
agent_framework (SPEC-002) por composição/herança - ver
docs/ARQUITETURA.md, tabela "Mapeamento para as SPECs", para o racional
dessa decisão.

Contrato (ver tests/test_gateway.py e docs/CRITERIOS-DE-ACEITE.md):
- Recebe {"message": str, "conversation_id": str | None}
- Normaliza via gateway.channel_gateway.normalize() (ChannelMessage real)
- Delega para orchestrator.graph.run_interaction()
- Retorna {"conversation_id": str, "response": str}
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

from gateway.channel_gateway import normalize
from gateway.health import report_health
from orchestrator.graph import run_interaction

app = FastAPI(title="PoC Agente de Catálogo")


class InteractRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class InteractResponse(BaseModel):
    conversation_id: str
    response: str


@app.get("/health")
def health():
    return report_health()


@app.post("/agent/interact", response_model=InteractResponse)
def interact(request: InteractRequest):
    interaction = normalize(request.message, conversation_id=request.conversation_id)
    response_text = run_interaction(interaction)
    return InteractResponse(conversation_id=interaction.session_id, response=response_text)
