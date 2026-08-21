"""Contratos do gateway.

ChannelMessage é o contrato canônico (agent_framework nativo).
Interaction é mantido como alias para compatibilidade com testes existentes.
"""

from pydantic import BaseModel

from agent_framework.channels.base import ChannelMessage

# Alias de compatibilidade — novos módulos devem usar ChannelMessage diretamente
Interaction = ChannelMessage


class HandoffPayload(BaseModel):
    """Payload de handoff bidirecional entre agentes.

    Campos:
      conversation_id   — ID da conversa em andamento (propaga o contexto SSE)
      origem_agente     — nome do agente que originou o handoff (ex: "agente_contas")
      contexto          — dados estruturados da interação anterior (plano atual, histórico, etc.)
      intencao_sugerida — texto que representa a intenção detectada pelo agente de origem
      protocolo         — número de protocolo gerado pelo agente de origem (opcional)
    """

    conversation_id: str
    origem_agente: str
    contexto: dict
    intencao_sugerida: str
    protocolo: str | None = None
