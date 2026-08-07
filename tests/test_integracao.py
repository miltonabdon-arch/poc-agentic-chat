"""Testes de integracao ponta a ponta - docs/CRITERIOS-DE-ACEITE.md.

Requerem ingestao ja realizada e o LLM_PROVIDER do agent_framework
configurado (ver .env.example - LLM_PROVIDER=mock funciona sem credencial
de nuvem) - marcados com @pytest.mark.integration para serem excluidos do
lint/testes rapidos de PR e rodados separadamente no Checkpoint 2 do
cronograma (ver docs/PROPOSTA-POC.md).
"""

import os

import pytest

from gateway.channel_gateway import normalize
from orchestrator.graph import run_interaction

pytestmark = pytest.mark.integration

_SKIP_REASON = "Requer LLM_PROVIDER configurado e ingestão prévia (ver docs/CRITERIOS-DE-ACEITE.md)"


@pytest.mark.skipif(not os.environ.get("LLM_PROVIDER"), reason=_SKIP_REASON)
def test_pergunta_fundamentada_retorna_resposta_com_fonte():
    interaction = normalize("Quais franquias de dados o Plano Turbo 40GB inclui?")
    resposta = run_interaction(interaction)
    assert "40GB" in resposta


@pytest.mark.skipif(not os.environ.get("LLM_PROVIDER"), reason=_SKIP_REASON)
def test_pergunta_fora_do_catalogo_retorna_nao_encontrado():
    interaction = normalize("Qual o preço do Plano Estratosférico 500GB?")
    resposta = run_interaction(interaction)
    assert "não encontrei" in resposta.lower()


@pytest.mark.skipif(not os.environ.get("LLM_PROVIDER"), reason=_SKIP_REASON)
def test_pergunta_com_cpf_e_mascarada_no_trace():
    interaction = normalize("Meu CPF é 123.456.789-00, qual meu plano atual?")
    resposta = run_interaction(interaction)
    assert "123.456.789-00" not in resposta
