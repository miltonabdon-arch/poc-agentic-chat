"""Testes de integração ponta a ponta — docs/CRITERIOS-DE-ACEITE.md.

A maioria requer ingestão prévia e LLM configurado (ver .env.example) e é
marcada individualmente com @pytest.mark.integration para ser excluída do
CI rápido (pytest -m "not integration"). Os 2 testes que exercitam apenas
roteamento/guardrails sem chamar o LLM (cancelamento e mascaramento de CPF)
NÃO recebem esse marker — devem rodar sempre, inclusive no CI rápido.

Nota histórica (ver STATE.md, achado 2026-08-20): antes desta versão, um
`pytestmark = pytest.mark.integration` no topo do módulo marcava TODOS os
testes do arquivo, incluindo os 2 que não usam LLM — por isso uma asserção
quebrada em test_intencao_cancelamento_roteia_para_handoff ficou invisível
para o CI por vários commits.
"""

import os

import pytest
from agent_framework.channels.base import ChannelMessage

from orchestrator.graph import run_interaction

_SKIP_LLM = "Requer LLM_BASE_URL/LLM_API_KEY configurados e ingestão prévia"


def _msg(text: str, session_id: str = "test-session") -> ChannelMessage:
    return ChannelMessage(
        channel="test",
        channel_id="poc",
        session_id=session_id,
        user_id="test-user",
        text=text,
    )


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_fundamentada_retorna_resposta_com_fonte():
    resposta = await run_interaction(_msg("Quais franquias de dados o Plano Turbo 40GB inclui?"))
    assert "40GB" in resposta or "40" in resposta


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_fora_do_catalogo_retorna_nao_encontrado():
    resposta = await run_interaction(_msg("Qual o preço do Plano Estratosférico 500GB?"))
    assert "não encontrei" in resposta.lower() or "não" in resposta.lower()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_com_cpf_e_mascarada_no_trace():
    resposta = await run_interaction(_msg("Meu CPF é 123.456.789-00, qual meu plano atual?"))
    assert "123.456.789-00" not in resposta


@pytest.mark.asyncio
async def test_intencao_cancelamento_roteia_para_handoff():
    """Sem LLM — valida que o roteador direciona cancelamento para handoff
    e que a resposta de fallback (mock offline) é uma string não vazia.

    A asserção verifica "cancelar" (não "cancelamento"): é a palavra que
    mock_services/agents/cancellation.py de fato usa em toda resposta
    ("Entendo que deseja cancelar. {oferta}") — assertar "cancelamento"
    fazia este teste falhar sempre (ver STATE.md, achado 2026-08-20).
    """
    resposta = await run_interaction(_msg("Quero cancelar minha linha."))
    assert isinstance(resposta, str)
    assert len(resposta) > 10
    assert "cancelar" in resposta.lower()


@pytest.mark.asyncio
async def test_guardrail_input_mascara_cpf():
    """Sem LLM — valida que CPF não aparece na resposta final."""
    resposta = await run_interaction(_msg("Meu CPF é 987.654.321-00"))
    assert "987.654.321-00" not in resposta


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_billing_retorna_resposta_natural():
    resposta = await run_interaction(_msg("Qual o valor da minha fatura?"))
    assert isinstance(resposta, str) and len(resposta) > 10


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_eligibility_retorna_resposta_natural():
    resposta = await run_interaction(_msg("Posso trocar de plano?"))
    assert isinstance(resposta, str) and len(resposta) > 10


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_simulation_retorna_resposta_natural():
    resposta = await run_interaction(_msg("Simula troca para turbo 40gb"))
    assert isinstance(resposta, str) and len(resposta) > 10
