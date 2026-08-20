from agents.plans import router as plans_router
import logging
import time

from agents.cancellation import router as cancellation_router
from agents.deals import router as deals_router
from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Agents Service TIM")

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


@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Crivo/Score — elegibilidade de ativação Pré-pago → Controle (Escopo v1.2 § 10)
# ---------------------------------------------------------------------------

_CRIVO_SCORE = {
    "12345678900": {
        "elegivel": True,
        "score": 720,
        "motivo": None,
    },
}


@app.get("/crivo/score/{cpf}")
def get_crivo_score(cpf: str):
    return _CRIVO_SCORE.get(
        cpf,
        {"elegivel": True, "score": 650, "motivo": None},
    )


# ---------------------------------------------------------------------------
# Catálogo de Ofertas Pré — planos disponíveis para ativação (Escopo v1.2 § 3.2)
# ---------------------------------------------------------------------------

_CATALOGO_PRE = {
    "ofertas": [
        {
            "id": "controle-basic",
            "nome": "TIM Controle Basic",
            "preco": 49.90,
            "descricao": "25 GB + ligações ilimitadas",
        },
        {
            "id": "controle-plus",
            "nome": "TIM Controle Plus",
            "preco": 69.90,
            "descricao": "50 GB + ligações ilimitadas + TIM Music",
        },
        {
            "id": "controle-top",
            "nome": "TIM Controle Top",
            "preco": 89.90,
            "descricao": "100 GB + ligações ilimitadas + TIM Music + TIM TV",
        },
    ]
}


@app.get("/catalogo/pre")
def get_catalogo_pre():
    return _CATALOGO_PRE


# ---------------------------------------------------------------------------
# Catálogo de Retenção — CAN-01/02/04 (Escopo v1.2 § 3.4)
# ---------------------------------------------------------------------------

_CATALOGO_RETENCAO = {
    "12345678900": {
        "ofertas": [
            {
                "id": "ret-001",
                "descricao": "3 meses com 50% de desconto + 10 GB extras por 6 meses",
                "desconto_percentual": 50,
                "meses_desconto": 3,
                "gb_extras": 10,
            },
            {
                "id": "ret-002",
                "descricao": "Upgrade para o próximo plano pelo mesmo preço por 6 meses",
                "desconto_percentual": 0,
                "meses_desconto": 6,
                "gb_extras": 0,
            },
        ],
        "isencao_multa": True,
    },
}


@app.get("/catalogo/retencao/{cpf}")
def get_catalogo_retencao(cpf: str):
    return _CATALOGO_RETENCAO.get(
        cpf,
        {
            "ofertas": [
                {
                    "id": "ret-padrao",
                    "descricao": "2 meses com 30% de desconto no plano atual",
                    "desconto_percentual": 30,
                    "meses_desconto": 2,
                    "gb_extras": 0,
                }
            ],
            "isencao_multa": False,
        },
    )


# ---------------------------------------------------------------------------
# Catálogo de Reversão — CAN-03 (Escopo v1.2 § 3.4)
# ---------------------------------------------------------------------------

_CATALOGO_REVERSAO = {
    "12345678900": {
        "oferta_reversao": {
            "id": "rev-001",
            "descricao": "Manutenção do plano com 1 mês grátis e sem cobrança de multa",
        },
        "isencao_multa": True,
    },
}


@app.get("/catalogo/reversao/{cpf}")
def get_catalogo_reversao(cpf: str):
    return _CATALOGO_REVERSAO.get(
        cpf,
        {
            "oferta_reversao": {
                "id": "rev-padrao",
                "descricao": "Reversão do cancelamento sem custos adicionais",
            },
            "isencao_multa": True,
        },
    )


# ---------------------------------------------------------------------------
# ATH — Atendimento Humano (CAN-05, Escopo v1.2 § 3.4)
# ---------------------------------------------------------------------------

@app.post("/ath/transbordo")
def ath_transbordo(body: dict):
    protocolo = f"ATH-{str(body.get('conversation_id', 'UNKNOWN'))[:8].upper()}"
    return {
        "protocolo": protocolo,
        "status": "aguardando_atendente",
        "previsao_espera_minutos": 5,
    }


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

@app.get("/crm/cliente/{cpf}")
def get_cliente(cpf: str):
    return {
        "cpf": cpf,
        "nome": "João Silva",
        "segmento": "premium",
        "plano_atual": "TIM Black 30GB",
        "mensalidade": 79.90,
    }
