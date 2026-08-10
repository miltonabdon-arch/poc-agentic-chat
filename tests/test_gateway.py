"""Testes do gateway (Backend/Integracao) - docs/PAPEIS-E-ENTREGAVEIS.md."""

from fastapi.testclient import TestClient

from gateway.app import app
from gateway.channel_gateway import normalize
from gateway.health import report_health

client = TestClient(app)


def test_health_retorna_ok():
    assert report_health() == {"status": "ok"}


def test_normalize_gera_interaction_com_conversation_id():
    interaction = normalize("Qual a franquia do plano turbo?")
    assert interaction.channel == "mock_sse"
    assert interaction.message == "Qual a franquia do plano turbo?"
    assert interaction.conversation_id


def test_normalize_reusa_conversation_id_quando_fornecido():
    interaction = normalize("Segunda pergunta", conversation_id="abc-123")
    assert interaction.conversation_id == "abc-123"


def test_interact_com_corpo_malformado_retorna_422():
    response = client.post("/agent/interact", json={"conversation_id": "abc-123"})
    assert response.status_code == 422
