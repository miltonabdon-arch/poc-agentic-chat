"""Router / Grafo - equivalente simplificado do Enterprise Router do
agent_platform_oci (LangGraph workflow).

Fluxo esperado (ver docs/ARQUITETURA.md, diagrama de sequencia):
Interaction -> guardrail de input -> agente (RAG + prompt + LLM) ->
guardrail de output -> resposta final. Cada etapa deve ser rastreada via
orchestrator/tracer.py.

TODO (AI Developer Sr): implementar o grafo LangGraph e run_interaction()
para satisfazer os testes de tests/test_integracao.py.

Pontos de atenção:
- Se o guardrail de input bloquear (Action.BLOCK), o fluxo deve pular
  direto para uma resposta de recusa, sem chamar o agente/LLM
- Se a consulta RAG não encontrar evidência (QueryResult.found=False), a
  resposta deve ser a padrão de "não encontrei" (agent.prompt.not_found_response()),
  sem chamar o LLM
- A resposta final deve passar pelo guardrail de output antes de retornar
- Cada interação deve ser envolvida por orchestrator.tracer.trace_interaction()
"""

from typing import TypedDict

from gateway.models import Interaction

import httpx

class GraphState(TypedDict):
    conversation_id: str
    input_text: str
    guarded_input: str
    response: str
    blocked: bool


def build_graph():
    raise NotImplementedError


MOCK_BASE = "http://mock-services:8001"
MOCK_CPF = "12345678900"  # CPF fixo enquanto não há autenticação real


def run_interaction(interaction: Interaction) -> str:
    intencao = detectar_intencao(interaction.message)
    if intencao in ("cancellation", "deals"):
        return handoff(intencao, interaction.message, interaction.conversation_id)
    if intencao == "billing":
        return responder_billing(interaction.conversation_id)
    if intencao == "elegibilidade":
        return responder_elegibilidade(interaction.conversation_id)
    if intencao == "simulacao_troca":
        return responder_simulacao_troca(interaction.message, interaction.conversation_id)
    return "Resposta simulada do agente (a ser implementada no grafo LangGraph) " + interaction.message


def detectar_intencao(texto: str) -> str:
    texto = texto.lower()
    if any(p in texto for p in ["cancelar", "cancelamento", "sair", "desativar"]):
        return "cancellation"
    if any(p in texto for p in ["simular", "simulação", "vale a pena trocar", "quanto vou pagar se"]):
        return "simulacao_troca"
    if any(p in texto for p in ["posso trocar", "posso mudar", "trocar de plano", "mudar de plano", "elegibilidade", "fidelidade", "multa"]):
        return "elegibilidade"
    if any(p in texto for p in ["oferta", "promoção", "upgrade", "planos disponíveis", "quais planos"]):
        return "deals"
    if any(p in texto for p in ["segunda via", "boleto", "fatura", "conta", "vencimento", "pagamento"]):
        return "billing"
    return "catalog"


def consultar_crm(cpf: str) -> dict:
    resp = httpx.get(f"{MOCK_BASE}/crm/cliente/{cpf}")
    return resp.json()


def responder_billing(conversation_id: str) -> str:
    cliente = consultar_crm(MOCK_CPF)
    nome = cliente.get("nome", "cliente")
    plano = cliente.get("plano_atual", "seu plano")
    mensalidade = cliente.get("mensalidade", 0)
    return (
        f"Olá, {nome}! Sua fatura do {plano} é de R${mensalidade:.2f}. "
        "Posso enviar a segunda via por e-mail ou SMS. Qual prefere?"
    )


def handoff(intencao: str, message: str, conversation_id: str) -> str:
    endpoint = f"{MOCK_BASE}/agent/{intencao}/interact"
    resp = httpx.post(endpoint, json={"message": message,
                                      "conversation_id": conversation_id})
    return resp.json()["response"]


def consultar_elegibilidade(cpf: str) -> dict:
    resp = httpx.get(f"{MOCK_BASE}/crm/cliente/{cpf}/elegibilidade")
    return resp.json()


def responder_elegibilidade(conversation_id: str) -> str:
    cliente = consultar_crm(MOCK_CPF)
    elegibilidade = consultar_elegibilidade(MOCK_CPF)
    nome = cliente.get("nome", "cliente")
    if not elegibilidade["pode_trocar"]:
        return f"Olá, {nome}! No momento não é possível realizar a troca de plano. Entre em contato com o suporte para mais detalhes."
    if elegibilidade["fidelidade_ativa"]:
        planos = ", ".join(elegibilidade["planos_disponiveis"])
        return (
            f"Olá, {nome}! Você pode trocar de plano, mas está em fidelidade até {elegibilidade['fim_fidelidade']}. "
            f"A multa por cancelamento antecipado é de R${elegibilidade['multa_cancelamento']:.2f}. "
            f"Planos disponíveis para migração: {planos}. Deseja simular a troca?"
        )
    planos = ", ".join(elegibilidade["planos_disponiveis"])
    return (
        f"Olá, {nome}! Você está livre para trocar de plano sem multa. "
        f"Planos disponíveis: {planos}. Posso simular quanto ficaria em cada um deles."
    )


def responder_simulacao_troca(message: str, conversation_id: str) -> str:
    plano_destino = _extrair_plano_da_mensagem(message)
    if plano_destino is None:
        elegibilidade = consultar_elegibilidade(MOCK_CPF)
        planos = ", ".join(elegibilidade.get("planos_disponiveis", []))
        return f"Qual plano você gostaria de simular? Temos disponíveis: {planos}."
    resp = httpx.post(
        f"{MOCK_BASE}/planos/simular-troca",
        json={"cpf": MOCK_CPF, "plano_destino": plano_destino},
    )
    data = resp.json()
    if "erro" in data:
        return f"Não consegui simular a troca: {data['erro']}"
    sinal = "+" if data["diferenca_mensal"] >= 0 else ""
    multa_txt = (
        f" Como você está em fidelidade, há uma multa de R${data['multa_se_aplicavel']:.2f}."
        if data["multa_se_aplicavel"] > 0
        else ""
    )
    return (
        f"Simulação de troca: {data['plano_atual']} → {data['plano_destino']}. "
        f"Mensalidade atual: R${data['mensalidade_atual']:.2f} | Nova mensalidade: R${data['mensalidade_destino']:.2f} "
        f"(diferença: {sinal}R${data['diferenca_mensal']:.2f}/mês).{multa_txt} "
        f"Vigência a partir do {data['data_vigencia']}. Deseja confirmar a troca?"
    )


_PLANO_ALIAS = {
    "turbo 40": "turbo-40gb",
    "turbo 40gb": "turbo-40gb",
    "turbo-40gb": "turbo-40gb",
    "controle 50": "controle-50gb",
    "controle 50gb": "controle-50gb",
    "controle-50gb": "controle-50gb",
    "controle 100": "controle-100gb",
    "controle 100gb": "controle-100gb",
    "família prime": "familia-prime",
    "familia prime": "familia-prime",
    "familia-prime": "familia-prime",
    "pré-pago turbo": "pre-pago-turbo",
    "pre-pago turbo": "pre-pago-turbo",
}


def _extrair_plano_da_mensagem(texto: str) -> str | None:
    texto = texto.lower()
    for alias, plano_id in _PLANO_ALIAS.items():
        if alias in texto:
            return plano_id
    return None

