"""Orquestrador LangGraph — AI Developer Sr (Igor Scaglia).

Responsabilidade: montar o grafo que une as fatias dos colegas usando
os contratos definidos em ARQUITETURA.md como cola entre as partes.

  Ana Carolina  → QueryResult      (rag_pipeline/query_api.py)
  Gustavo       → GuardrailResult  (agent/guardrails/, branch test_new_branch)
  Kirllen       → ChannelMessage   (gateway/channel_gateway.py, branch backend)
  Igor (este arquivo) → build_graph(), run_interaction(), _run_catalog(), etc.

Fluxo do grafo (PAPEIS-E-ENTREGAVEIS.md — AI Developer Sr / Escopo v1.2):
  input_guardrails → routing_decision → [informacao|cancelamento|
  ativacao|mudanca_plano|supervisor] → output_guardrails → judge → END

  Jornada informacao: catálogo TIM X + subcaso cobrança (fatura/segunda via)
  Jornada cancelamento: retenção CAN-01..05 + ATH (✓ Passo 5)
  Jornada ativacao: Crivo/Score + Catálogo Pré (✓ Passo 3)
  Jornada mudanca_plano: elegibilidade + simulação unificadas (✓ Passo 4)

Expansão sobre o framework:
  O agent_platform_oci fornece EnterpriseRouter e ChannelMessage, mas NÃO
  monta o StateGraph — essa topologia (nós, arestas, condicionais) é
  responsabilidade explícita do AI Developer Sr (ver PAPEIS-E-ENTREGAVEIS.md).
"""

from __future__ import annotations

import logging
import os
import time
from types import SimpleNamespace
from typing import Any

import httpx
from agent_framework.channels.base import ChannelMessage
from agent_framework.routing.enterprise_router import EnterpriseRouter
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from orchestrator.tracer import log_sumario_interacao, trace_interaction

logger = logging.getLogger(__name__)

MOCK_BASE = os.environ.get("MOCK_SERVICES_URL", "http://localhost:8001")
MOCK_CPF = "12345678900"

_router_settings = SimpleNamespace(
    ROUTING_CONFIG_PATH="orchestrator/routing_config.yaml",
    ENABLE_LLM_ROUTER=False,
)
_router = EnterpriseRouter(_router_settings)


# ---------------------------------------------------------------------------
# Estado do grafo
# ---------------------------------------------------------------------------

class GraphState(TypedDict):
    channel_message: ChannelMessage
    sanitized_input: str       # saída do input_guardrail (PII mascarado ou texto original)
    route: str                 # agente escolhido pelo EnterpriseRouter
    intent: str
    answer: str
    final_answer: str
    blocked: bool
    guardrail_decisions: list[Any]
    # chunk_id: adicionado pelo AI Dev Sr para propagar o identificador do
    # documento RAG até o sumário de observabilidade (CRITERIOS-DE-ACEITE §6).
    # O agent_framework não carrega esse campo — é extensão local da PoC.
    chunk_id: str | None
    # handoff_origem: preenchido quando outra jornada ou agente externo transfere
    # a conversa para cá. Valor "agente_contas" pula a etapa de elegibilidade na
    # jornada de Mudança de Plano (Subfluxo Contas — Escopo v1.2 § 3.3).
    handoff_origem: str | None
    # protocolo_id: gerado pelo node_judge ao final do fluxo e propagado ao SUMARIO.
    # Segue o padrão "PROT-{8 primeiros chars do session_id em maiúsculas}".
    protocolo_id: str | None


# ---------------------------------------------------------------------------
# Helpers de roteamento interno da jornada de Informação (Escopo v1.2 § 3.1)
# ---------------------------------------------------------------------------

# Espelho das palavras_cobranca declaradas em routing_config.yaml.
# Usadas para detectar o subcaso cobrança DENTRO da jornada de Informação,
# sem criar um nó/rota separada no grafo.
_PALAVRAS_COBRANCA = frozenset({
    "fatura", "boleto", "pagamento", "vencimento",
    "segunda via", "débito automático", "cobrança",
})


def _eh_subcaso_cobranca(text: str) -> bool:
    """Retorna True se o texto indica dúvida de fatura/cobrança."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _PALAVRAS_COBRANCA)


# ---------------------------------------------------------------------------
# Nós do grafo — Escopo v1.2
# ---------------------------------------------------------------------------

async def node_input_guardrails(state: GraphState) -> GraphState:
    from agent.guardrails.input_guardrail import check_input
    from agent.models import Action

    result = check_input(state["channel_message"].text)
    blocked = result.action_taken == Action.BLOCK
    await trace_interaction(
        "GRL",
        state["channel_message"],
        {"guardrail": "input", "violation": result.violation.value, "blocked": blocked},
    )
    return {
        **state,
        "sanitized_input": result.text,
        "blocked": blocked,
        "guardrail_decisions": [result],
    }


async def node_routing_decision(state: GraphState) -> GraphState:
    decision = await _router.route({"sanitized_input": state["sanitized_input"]})
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "routing_decision", "intent": decision.intent, "agent": decision.agent},
    )
    return {**state, "route": decision.agent, "intent": decision.intent}


async def node_informacao(state: GraphState) -> GraphState:
    """Jornada de Informação (Escopo v1.2 § 3.1).

    Detecta internamente se é subcaso cobrança (fatura/segunda via) antes de
    consultar o catálogo RAG. O subcaso cobrança consulta o CRM primeiro para
    identificar contrato e segmento do cliente.
    """
    if _eh_subcaso_cobranca(state["sanitized_input"]):
        answer = await _run_subcaso_cobranca(state["sanitized_input"], state["channel_message"])
        await trace_interaction(
            "NOC",
            state["channel_message"],
            {"node": "informacao", "subcaso": "cobrança"},
        )
        return {**state, "answer": answer}

    # Subcaso catálogo: _run_catalog retorna (resposta, chunk_id) para o sumário
    # de observabilidade — ver CRITERIOS-DE-ACEITE §6.
    answer, chunk_id = await _run_catalog(state["sanitized_input"], state["channel_message"])
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "informacao", "subcaso": "catalog", "chunk_id": chunk_id},
    )
    return {**state, "answer": answer, "chunk_id": chunk_id}


async def node_cancelamento_retencao(state: GraphState) -> GraphState:
    """Jornada de Cancelamento — retenção e reversão (Escopo v1.2 § 3.4).

    CAN-01: Catálogo de Retenção.
    CAN-02: Apresentação de contra-oferta de retenção.
    CAN-03: Catálogo de Reversão (cliente que já cancelou e quer voltar atrás).
    CAN-04: Isenção de multa incluída na oferta quando elegível.
    CAN-05: Transbordo para ATH apenas em exceção negocial (sem ofertas disponíveis).
    """
    answer = await _run_cancelamento_retencao(state["sanitized_input"], state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "cancelamento_retencao"})
    return {**state, "answer": answer}


async def node_ativacao(state: GraphState) -> GraphState:
    """Jornada de Ativação — migração Pré-pago → Controle (Escopo v1.2 § 3.2 & 10).

    Sem handoff externo: consulta Crivo/Score e Catálogo de Ofertas Pré
    diretamente nesta jornada, sem acionar agente externo.
    """
    answer = await _run_ativacao(state["sanitized_input"], state["channel_message"])
    await trace_interaction("NOC", state["channel_message"], {"node": "ativacao"})
    return {**state, "answer": answer}


async def node_mudanca_plano(state: GraphState) -> GraphState:
    """Jornada de Mudança de Plano — Up/Down (Escopo v1.2 § 3.3).

    Elegibilidade e simulação são etapas sequenciais do mesmo fluxo (não mais nós separados).
    Subfluxo Contas: quando handoff_origem == "agente_contas", pula a etapa de
    elegibilidade e vai direto para simulação/aplicação do plano.
    """
    answer = await _run_mudanca_plano(
        state["sanitized_input"],
        state["channel_message"],
        state.get("handoff_origem"),
    )
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "mudanca_plano", "handoff_origem": state.get("handoff_origem")},
    )
    return {**state, "answer": answer}


async def node_supervisor(state: GraphState) -> GraphState:
    await trace_interaction("NOC", state["channel_message"], {"node": "supervisor"})
    return {
        **state,
        "answer": (
            "Olá! Sou o assistente TIM. Posso ajudar com planos, fatura, "
            "cancelamento ou negociação. Como posso te ajudar?"
        ),
    }


async def node_output_guardrails(state: GraphState) -> GraphState:
    from agent.guardrails.output_guardrail import check_output

    result = check_output(state["answer"], intent=state.get("intent"))
    await trace_interaction(
        "GRL",
        state["channel_message"],
        {"guardrail": "output", "violation": result.violation.value},
    )
    decisions = list(state.get("guardrail_decisions") or [])
    decisions.append(result)
    return {**state, "final_answer": result.text, "guardrail_decisions": decisions}


async def node_judge(state: GraphState) -> GraphState:
    from agent.judge import judge_batch

    session_id = state["channel_message"].session_id
    protocolo_id = f"PROT-{session_id[:8].upper()}"

    try:
        judge_batch([{
            "interaction_id": session_id,
            "response": state["final_answer"],
            "source_document_id": None,
        }])
    except Exception:
        logger.warning("judge_batch falhou, continuando", exc_info=True)
    await trace_interaction(
        "NOC",
        state["channel_message"],
        {"node": "judge", "protocolo": protocolo_id},
    )
    return {**state, "protocolo_id": protocolo_id}


# ---------------------------------------------------------------------------
# Lógica de roteamento condicional
# ---------------------------------------------------------------------------

def _after_guardrails(state: GraphState) -> str:
    return END if state["blocked"] else "routing_decision"


def _after_routing(state: GraphState) -> str:
    route = state.get("route", "supervisor_agent")
    # Nomes dos agentes alinhados ao routing_config.yaml (Escopo v1.2 § 3.x).
    # Os nós do grafo ainda usam os nomes anteriores enquanto as implementações
    # de cada jornada não forem refatoradas (Passos 2-5 do plano de evolução).
    _map = {
        "informacao_agent":    "informacao",           # Passo 2: ✓ jornada Informação (catálogo + cobrança)
        "cancelamento_agent":  "cancelamento_retencao", # Passo 5: ✓ retenção CAN-01..05 + ATH
        "ativacao_agent":      "ativacao",              # Passo 3: ✓ Crivo/Score + Catálogo Pré (sem handoff)
        "mudanca_plano_agent": "mudanca_plano",         # Passo 4: ✓ elegibilidade + simulação unificadas
        "supervisor_agent":    "supervisor",
    }
    return _map.get(route, "supervisor")


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(GraphState)

    g.add_node("input_guardrails", node_input_guardrails)
    g.add_node("routing_decision", node_routing_decision)
    g.add_node("informacao", node_informacao)           # Passo 2: ✓ catalog + cobrança como subcaso
    g.add_node("cancelamento_retencao", node_cancelamento_retencao)
    g.add_node("ativacao", node_ativacao)               # Passo 3: ✓ Crivo/Score + Catálogo Pré
    g.add_node("mudanca_plano", node_mudanca_plano)    # Passo 4: ✓ elegibilidade + simulação unificadas
    g.add_node("supervisor", node_supervisor)
    g.add_node("output_guardrails", node_output_guardrails)
    g.add_node("judge", node_judge)

    g.set_entry_point("input_guardrails")
    g.add_conditional_edges("input_guardrails", _after_guardrails)
    g.add_conditional_edges(
        "routing_decision",
        _after_routing,
        {
            "informacao": "informacao",
            "cancelamento_retencao": "cancelamento_retencao",
            "ativacao": "ativacao",
            "mudanca_plano": "mudanca_plano",
            "supervisor": "supervisor",
        },
    )
    for node in [
        "informacao",
        "cancelamento_retencao",
        "ativacao",
        "mudanca_plano",
        "supervisor",
    ]:
        g.add_edge(node, "output_guardrails")
    g.add_edge("output_guardrails", "judge")
    g.add_edge("judge", END)

    return g


_compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Entrypoint público
# ---------------------------------------------------------------------------

async def run_interaction(
    channel_message: ChannelMessage,
    config: dict | None = None,
    handoff_origem: str | None = None,
) -> str:
    await trace_interaction("IC", channel_message, {"text": channel_message.text})

    t_inicio = time.perf_counter()

    initial_state = GraphState(
        channel_message=channel_message,
        sanitized_input="",
        route="",
        intent="",
        answer="",
        final_answer="",
        blocked=False,
        guardrail_decisions=[],
        chunk_id=None,
        handoff_origem=handoff_origem,
        protocolo_id=None,
    )

    final_state = await _compiled_graph.ainvoke(initial_state, config=config or {})

    # Sumário de observabilidade ao final do fluxo — CRITERIOS-DE-ACEITE §6.
    # Agrega latência total, chunk usado e guardrails acionados numa linha legível.
    latencia_ms = int((time.perf_counter() - t_inicio) * 1000)
    log_sumario_interacao(
        channel_message=channel_message,
        latencia_ms=latencia_ms,
        chunk_id=final_state.get("chunk_id"),
        guardrail_decisions=final_state.get("guardrail_decisions") or [],
    )

    # Publica SUMARIO no broadcaster — Chainlit e SSE usam para finalizar o fluxo visual.
    from orchestrator.trace_broadcaster import get_broadcaster
    await get_broadcaster().publish({
        "type": "SUMARIO",
        "session_id": channel_message.session_id,
        "latencia_ms": latencia_ms,
        "chunk_id": final_state.get("chunk_id"),
        "protocolo_id": final_state.get("protocolo_id"),
    })

    if final_state.get("blocked"):
        return (
            "Não consigo continuar o atendimento. "
            "Por favor, reformule sua mensagem para que eu possa te ajudar."
        )

    return final_state.get("final_answer") or final_state.get("answer") or ""


# ---------------------------------------------------------------------------
# Helpers de negócio (portados de Kirllen, adaptados para async + ChannelMessage)
# ---------------------------------------------------------------------------

async def _run_catalog(text: str, msg: ChannelMessage) -> tuple[str, str | None]:
    """Consulta o catálogo RAG e chama o LLM com o contexto encontrado.

    Retorna (resposta, chunk_id) para que o AI Dev Sr propague o chunk_id
    ao estado do grafo e ao sumário de observabilidade (§6).

    Colaboração:
      - QueryResult vem de Ana (rag_pipeline/query_api.py)
      - build_prompt / not_found_response vem de Gustavo (agent/prompt.py)
      - complete() usa llm_client configurado pelo AI Dev Sr para Flow CI&T
    """
    try:
        from agent.llm_client import complete
        from agent.prompt import build_prompt, not_found_response
        from rag_pipeline.query_api import query
        from rag_pipeline.vectorizer import get_client

        chroma_client = get_client()
        # Decisão: get_client() usa path absoluto (vectorizer.py) para evitar
        # problema de cwd relativo quando o uvicorn muda de diretório.
        result = query(chroma_client, text)
        if not result.found:
            return not_found_response(), None
        prompt = build_prompt(text, result)
        if prompt is None:
            # build_prompt retorna None quando found=False — nunca deve chegar
            # aqui, mas tratamos por segurança (contrato de Gustavo).
            return not_found_response(), None
        return complete(prompt), result.chunk_id
    except Exception:
        logger.warning("catalog_agent falhou, usando fallback", exc_info=True)
        return "Não consegui acessar o catálogo no momento. Tente novamente.", None


async def _run_subcaso_cobranca(text: str, msg: ChannelMessage) -> str:
    """Subcaso cobrança dentro da jornada de Informação (Escopo v1.2 § 3.1).

    Consulta TIM/Clientes (CRM) primeiro para identificar contrato e segmento
    do cliente antes de responder à dúvida de cobrança ou emitir segunda via.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            cliente = r.json()
        nome = cliente.get("nome", "cliente")
        segmento = cliente.get("segmento", "padrão")
        plano = cliente.get("plano_atual", "seu plano")
        mensalidade = cliente.get("mensalidade", 0)
        pede_segunda_via = any(
            kw in text.lower()
            for kw in ("segunda via", "boleto", "pagar", "pagamento")
        )
        if pede_segunda_via:
            return (
                f"Olá, {nome}! Identifiquei seu contrato {segmento}: {plano}. "
                f"Sua fatura é de R${mensalidade:.2f}. "
                "Posso enviar a segunda via por e-mail ou SMS. Qual prefere?"
            )
        return (
            f"Olá, {nome}! Seu plano {plano} (segmento {segmento}) tem mensalidade "
            f"de R${mensalidade:.2f}. "
            "Tem alguma dúvida específica sobre sua cobrança?"
        )
    except Exception:
        logger.warning("subcaso_cobranca falhou", exc_info=True)
        return "Não consegui acessar as informações de fatura no momento."



async def _acionar_ath(msg: ChannelMessage, motivo: str) -> None:
    """CAN-05: dispara transbordo para Atendimento Humano (ATH) em exceção negocial."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{MOCK_BASE}/ath/transbordo",
                json={"conversation_id": msg.session_id, "motivo": motivo, "canal": "digital"},
            )
    except Exception:
        logger.warning("ath_transbordo falhou", exc_info=True)


async def _run_cancelamento_retencao(text: str, msg: ChannelMessage) -> str:
    """Jornada de Cancelamento: Retenção/Reversão + ATH (Escopo v1.2 § 3.4).

    CAN-01: GET /catalogo/retencao/{cpf} — ofertas de retenção do cliente.
    CAN-02: apresenta contra-oferta de retenção antes do cancelamento definitivo.
    CAN-03: GET /catalogo/reversao/{cpf} — quando cliente já cancelou e quer reverter.
    CAN-04: isencao_multa incluída na oferta vinda do catálogo quando elegível.
    CAN-05: POST /ath/transbordo — apenas se não houver ofertas disponíveis.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            cliente = r_crm.json()
        nome = cliente.get("nome", "cliente")
        plano = cliente.get("plano_atual", "seu plano")
        segmento = cliente.get("segmento", "padrão")

        # CAN-03: detectar solicitação de reversão (cliente já cancelou e quer voltar)
        pede_reversao = any(
            kw in text.lower()
            for kw in ("reverter", "desfazer", "mudei de ideia", "não quero mais cancelar", "voltei atrás")
        )
        if pede_reversao:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r_rev = await client.get(f"{MOCK_BASE}/catalogo/reversao/{MOCK_CPF}")
                reversao = r_rev.json()
            oferta = reversao.get("oferta_reversao", {})
            # CAN-04: isenção de multa vinda do catálogo de reversão
            msg_isencao = " Com isenção total de multa." if reversao.get("isencao_multa") else ""
            return (
                f"Olá, {nome}! Ficamos felizes em saber que reconsiderou. "
                f"Podemos reverter o cancelamento do seu {plano}.{msg_isencao} "
                f"Benefício: {oferta.get('descricao', 'manutenção do seu plano')}. "
                "Confirma a reversão?"
            )

        # CAN-01: Catálogo de Retenção
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_ret = await client.get(f"{MOCK_BASE}/catalogo/retencao/{MOCK_CPF}")
            retencao = r_ret.json()

        ofertas = retencao.get("ofertas", [])
        if not ofertas:
            # CAN-05: sem ofertas → transbordo para ATH
            await _acionar_ath(msg, motivo="sem_oferta_retencao")
            return (
                f"Olá, {nome}! Lamentamos sua decisão de cancelar o {plano}. "
                "Vou conectá-lo com um especialista que pode oferecer condições exclusivas. "
                "Aguarde um momento."
            )

        # CAN-02: apresentar melhor contra-oferta + CAN-04: isenção de multa
        melhor = ofertas[0]
        msg_isencao = " Sem cobrança de multa." if retencao.get("isencao_multa") else ""
        return (
            f"Olá, {nome}! Entendemos que deseja cancelar o {plano} (segmento {segmento}). "
            f"Antes de finalizar, temos uma oferta exclusiva para você: "
            f"{melhor['descricao']}.{msg_isencao} "
            "Gostaria de aproveitar essa condição?"
        )
    except Exception:
        logger.warning("cancelamento_retencao falhou", exc_info=True)
        return "Não consegui processar sua solicitação de cancelamento no momento. Tente novamente."


async def _run_ativacao(text: str, msg: ChannelMessage) -> str:
    """Jornada de Ativação: Crivo/Score → Catálogo Pré → apresentação da oferta (Escopo v1.2 § 3.2).

    Sem handoff externo: elegibilidade e oferta são resolvidas diretamente nesta jornada.
    Passo 1 — Crivo/Score: verifica se o cliente Pré-pago pode migrar para Controle.
    Passo 2 — Catálogo Pré: busca os planos disponíveis para ativação.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_score = await client.get(f"{MOCK_BASE}/crivo/score/{MOCK_CPF}")
            score = r_score.json()

        if not score.get("elegivel"):
            motivo = score.get("motivo", "critérios de crédito não atendidos")
            return (
                f"Infelizmente a ativação para Controle não está disponível agora. "
                f"Motivo: {motivo}. Posso ajudar com mais alguma coisa?"
            )

        async with httpx.AsyncClient(timeout=5.0) as client:
            r_catalogo = await client.get(f"{MOCK_BASE}/catalogo/pre")
            catalogo = r_catalogo.json()

        ofertas = catalogo.get("ofertas", [])
        if not ofertas:
            return "Não encontrei ofertas de ativação disponíveis no momento. Tente novamente mais tarde."

        linhas = [
            f"  • {o['nome']}: R${o['preco']:.2f}/mês — {o.get('descricao', '')}"
            for o in ofertas
        ]
        return (
            "Ótima notícia! Você está elegível para migrar para o Controle. "
            "Veja as opções disponíveis:\n"
            + "\n".join(linhas)
            + "\n\nQual dessas ofertas você gostaria de ativar?"
        )
    except Exception:
        logger.warning("ativacao falhou", exc_info=True)
        return "Não consegui acessar as ofertas de ativação no momento. Tente novamente."


async def _run_mudanca_plano(text: str, msg: ChannelMessage, handoff_origem: str | None) -> str:
    """Jornada de Mudança de Plano: Elegibilidade → Simulação (Escopo v1.2 § 3.3).

    Etapa 1 — Elegibilidade Completa: verifica se o cliente pode trocar de plano.
               Pulada quando handoff_origem == "agente_contas" (Subfluxo Contas).
    Etapa 2 — Simulação direta se plano-alvo detectado na mensagem; caso contrário,
               lista as opções disponíveis (Catálogo NBA para up, Retenção para down).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_crm = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}")
            r_eleg = await client.get(f"{MOCK_BASE}/crm/cliente/{MOCK_CPF}/elegibilidade")
            cliente = r_crm.json()
            elegibilidade = r_eleg.json()

        nome = cliente.get("nome", "cliente")

        # Etapa 1: verificação de elegibilidade — pulada no Subfluxo Contas
        if handoff_origem != "agente_contas" and not elegibilidade.get("pode_trocar"):
            return f"Olá, {nome}! No momento não é possível realizar a troca de plano."

        # Etapa 2: plano-alvo identificado na mensagem → simular diretamente
        plano_alvo = _extrair_plano(text)
        if plano_alvo:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r_sim = await client.post(
                    f"{MOCK_BASE}/planos/simular-troca",
                    json={"cpf": MOCK_CPF, "plano_destino": plano_alvo},
                )
                data = r_sim.json()
            if "erro" in data:
                return f"Não consegui simular a troca: {data['erro']}"
            sinal = "+" if data["diferenca_mensal"] >= 0 else ""
            multa = (
                f" Multa de fidelidade: R${data['multa_se_aplicavel']:.2f}."
                if data.get("multa_se_aplicavel", 0) > 0
                else ""
            )
            aviso_fidelidade = ""
            if elegibilidade.get("fidelidade_ativa") and handoff_origem != "agente_contas":
                aviso_fidelidade = (
                    f" Fidelidade ativa até {_fmt_data(elegibilidade.get('fim_fidelidade'))}."
                )
            return (
                f"Olá, {nome}! Simulação: {data['plano_atual']} → {data['plano_destino']}. "
                f"Atual: R${data['mensalidade_atual']:.2f} | Nova: R${data['mensalidade_destino']:.2f} "
                f"({sinal}R${data['diferenca_mensal']:.2f}/mês).{multa}{aviso_fidelidade} "
                f"Vigência: {_fmt_data(data['data_vigencia'])}. Confirma a troca?"
            )

        # Etapa 2 (sem plano-alvo): listar opções disponíveis
        planos_disp = elegibilidade.get("planos_disponiveis", [])
        planos_fmt = ", ".join(planos_disp) if planos_disp else "nenhum disponível"
        aviso_fidelidade = ""
        if elegibilidade.get("fidelidade_ativa"):
            aviso_fidelidade = (
                f" Você está em fidelidade até {_fmt_data(elegibilidade.get('fim_fidelidade'))} "
                f"(multa: R${elegibilidade.get('multa_cancelamento', 0):.2f})."
            )
        return (
            f"Olá, {nome}! Você pode trocar de plano.{aviso_fidelidade} "
            f"Planos disponíveis: {planos_fmt}. "
            "Qual plano você gostaria de simular?"
        )
    except Exception:
        logger.warning("mudanca_plano falhou", exc_info=True)
        return "Não consegui processar sua solicitação de mudança de plano no momento."


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


def _fmt_data(iso: str | None) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/YYYY'. Retorna o valor original se inválido."""
    if not iso:
        return iso or ""
    try:
        from datetime import date
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _extrair_plano(texto: str) -> str | None:
    texto = texto.lower()
    for alias, plano_id in _PLANO_ALIAS.items():
        if alias in texto:
            return plano_id
    return None
