import logging
import time

from agents.cancellation import router as cancellation_router
from agents.deals import router as deals_router
from agents.plans import router as plans_router
from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Agents Service TIM")

app.include_router(cancellation_router)
app.include_router(deals_router)
app.include_router(plans_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Loga cada request/response de forma estruturada.

    Visibilidade de que dados mockados foram servidos — essencial para
    distinguir, nos logs do compose, chamadas reais de dados sintéticos.
    """
    t0 = time.perf_counter()
    conversation_id = request.headers.get("x-conversation-id", "-")
    logger.info(
        "[MOCK] REQUEST | method=%s | path=%s | conversation_id=%s",
        request.method, request.url.path, conversation_id,
    )
    response = await call_next(request)
    latencia_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "[MOCK] RESPONSE | method=%s | path=%s | status=%d | latencia_ms=%d",
        request.method, request.url.path, response.status_code, latencia_ms,
    )
    return response


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
