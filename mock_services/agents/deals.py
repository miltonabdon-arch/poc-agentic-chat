from fastapi import APIRouter

router = APIRouter(prefix="/agent/deals")

OFERTAS = [
      {"id": "P001", "nome": "TIM Black 50GB", "preco": 89.90},
      {"id": "P002", "nome": "TIM Beta 100GB", "preco": 119.90},
      {"id": "P003", "nome": "TIM Controle 25GB", "preco": 55.00},
  ]

@router.post("/interact")
def interact(body: dict):
    return {
        "conversation_id": body.get("conversation_id"),
        "response": f"Temos {len(OFERTAS)} planos disponíveis: "
                    + ", ".join(f"{o['nome']} por R${o['preco']}" for o in OFERTAS),
        "ofertas": OFERTAS,
    }
