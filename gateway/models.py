"""Contratos do gateway.

ChannelMessage é o contrato canônico (agent_framework nativo).
Interaction é mantido como alias para compatibilidade com testes existentes.
"""

from agent_framework.channels.base import ChannelMessage

# Alias de compatibilidade — novos módulos devem usar ChannelMessage diretamente
Interaction = ChannelMessage
