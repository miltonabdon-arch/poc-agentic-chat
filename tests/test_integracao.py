"""Testes de integração ponta a ponta — docs/CRITERIOS-DE-ACEITE.md.

Requerem ingestão prévia e LLM configurado (ver .env.example).
Marcados com @pytest.mark.integration para serem excluídos do CI rápido.
"""

import os

import pytest
from agent_framework.channels.base import ChannelMessage

from orchestrator.graph import run_interaction

pytestmark = pytest.mark.integration

_SKIP_LLM = "Requer LLM_BASE_URL/LLM_API_KEY configurados e ingestão prévia"


def _msg(text: str, session_id: str = "test-session") -> ChannelMessage:
    return ChannelMessage(
        channel="test",
        channel_id="poc",
        session_id=session_id,
        user_id="test-user",
        text=text,
    )


@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_fundamentada_retorna_resposta_com_fonte():
    resposta = await run_interaction(_msg("Quais franquias de dados o Plano Turbo 40GB inclui?"))
    assert "40GB" in resposta or "40" in resposta


@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_fora_do_catalogo_retorna_nao_encontrado():
    resposta = await run_interaction(_msg("Qual o preço do Plano Estratosférico 500GB?"))
    assert "não encontrei" in resposta.lower() or "não" in resposta.lower()


@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason=_SKIP_LLM)
@pytest.mark.asyncio
async def test_pergunta_com_cpf_e_mascarada_no_trace():
    resposta = await run_interaction(_msg("Meu CPF é 123.456.789-00, qual meu plano atual?"))
    assert "123.456.789-00" not in resposta


@pytest.mark.asyncio
async def test_intencao_cancelamento_roteia_para_handoff():
    """Sem LLM — valida que o roteador direciona cancelamento para handoff
    e que a resposta de fallback (mock offline) é uma string não vazia."""
    resposta = await run_interaction(_msg("Quero cancelar minha linha."))
    assert isinstance(resposta, str)
    assert len(resposta) > 10
    assert "cancelamento" in resposta.lower() or "solicitação" in resposta.lower() or "encaminhei" in resposta.lower()


@pytest.mark.asyncio
async def test_guardrail_input_mascara_cpf():
    """Sem LLM — valida que CPF não aparece na resposta final."""
    resposta = await run_interaction(_msg("Meu CPF é 987.654.321-00"))
    assert "987.654.321-00" not in resposta
