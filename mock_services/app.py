from agents.cancellation import router as cancellation_router
from agents.deals import router as deals_router
from agents.plans import router as plans_router
from fastapi import FastAPI

app = FastAPI(title="Mock Agents Service TIM")

app.include_router(cancellation_router)
app.include_router(deals_router)
app.include_router(plans_router)

# Simula CRM
@app.get("/crm/cliente/{cpf}")
def get_cliente(cpf: str):
    return {
        "cpf": cpf,
        "nome": "João Silva",
        "segmento": "premium",
        "plano_atual": "TIM Black 30GB",
        "mensalidade": 79.90,
    }


@app.get("/health")
def health():
    return {"status": "ok"}