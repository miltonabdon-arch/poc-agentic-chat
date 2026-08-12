import random

from fastapi import APIRouter

router = APIRouter(prefix="/agent/cancellation")

CONTRA_OFERTAS = [
    "Posso oferecer 3 meses com 50% de desconto no seu plano atual.",
    "Temos um upgrade para TIM Black 50GB pelo mesmo preço que você paga hoje.",
    "Posso adicionar 10GB extras sem custo por 6 meses para você continuar.",
]


@router.post("/interact")
def interact(body: dict):
    msg = body.get("message", "").lower()
    oferta = random.choice(CONTRA_OFERTAS)
    return {
        "conversation_id": body.get("conversation_id"),
        "response": f"[Agente Retenção] Entendo que deseja cancelar. {oferta}",
        "handoff_resolvido": True,
    }