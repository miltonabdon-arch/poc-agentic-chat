from fastapi import APIRouter

router = APIRouter()

_ELEGIBILIDADE = {
    "12345678900": {
        "pode_trocar": True,
        "fidelidade_ativa": True,
        "fim_fidelidade": "2026-11-15",
        "multa_cancelamento": 120.00,
        "planos_disponiveis": ["controle-50gb", "turbo-40gb", "familia-prime"],
    },
}

_CATALOG = {
    "controle-50gb":  {"nome": "TIM Controle 50GB",  "preco": 69.90},
    "turbo-40gb":     {"nome": "TIM Turbo 40GB",      "preco": 89.90},
    "familia-prime":  {"nome": "TIM Família Prime",   "preco": 109.90},
    "controle-20gb":  {"nome": "TIM Controle 20GB",   "preco": 49.90},
    "controle-100gb": {"nome": "TIM Controle 100GB",  "preco": 99.90},
    "pre-pago-turbo": {"nome": "TIM Pré-Pago Turbo",  "preco": 29.90},
}

_CRM = {
    "12345678900": {"plano_atual_id": "controle-20gb", "mensalidade": 49.90},
}


@router.get("/crm/cliente/{cpf}/elegibilidade")
def get_elegibilidade(cpf: str):
    return _ELEGIBILIDADE.get(
        cpf,
        {
            "pode_trocar": True,
            "fidelidade_ativa": False,
            "fim_fidelidade": None,
            "multa_cancelamento": 0.0,
            "planos_disponiveis": list(_CATALOG.keys()),
        },
    )


@router.post("/planos/simular-troca")
def simular_troca(body: dict):
    cpf = body.get("cpf", "12345678900")
    destino_id = body.get("plano_destino", "")

    crm = _CRM.get(cpf, {"plano_atual_id": "controle-20gb", "mensalidade": 49.90})
    elegibilidade = _ELEGIBILIDADE.get(
        cpf,
        {"fidelidade_ativa": False, "multa_cancelamento": 0.0},
    )

    plano_atual = _CATALOG.get(crm["plano_atual_id"], {"nome": crm["plano_atual_id"], "preco": crm["mensalidade"]})
    plano_destino = _CATALOG.get(destino_id)

    if plano_destino is None:
        return {"erro": f"Plano '{destino_id}' não encontrado no catálogo."}

    diferenca = round(plano_destino["preco"] - plano_atual["preco"], 2)
    multa = elegibilidade["multa_cancelamento"] if elegibilidade["fidelidade_ativa"] else 0.0

    return {
        "plano_atual": plano_atual["nome"],
        "plano_destino": plano_destino["nome"],
        "mensalidade_atual": plano_atual["preco"],
        "mensalidade_destino": plano_destino["preco"],
        "diferenca_mensal": diferenca,
        "multa_se_aplicavel": multa,
        "data_vigencia": "próximo ciclo de faturamento",
    }
