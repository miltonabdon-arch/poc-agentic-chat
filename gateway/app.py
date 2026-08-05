"""Runtime FastAPI - wrapper minimo equivalente a AgentRuntimeMixin (SPEC-002).

Deve expor POST /agent/interact, delegando para o orquestrador
(orchestrator/graph.py).

TODO (Backend/Integração): implementar o endpoint POST /agent/interact.

Contrato (ver tests/test_gateway.py e docs/CRITERIOS-DE-ACEITE.md):
- Recebe {"message": str, "conversation_id": str | None}
- Normaliza via gateway.channel_gateway.normalize()
- Delega para orchestrator.graph.run_interaction()
- Retorna {"conversation_id": str, "response": str}
- GET /health já está implementado (gateway/health.py) e deve ser exposto
  aqui também
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

from gateway.health import report_health

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
    raise NotImplementedError
