"""Contrato Interaction - ver docs/ARQUITETURA.md.

Interaction e um alias fino sobre ChannelMessage do framework real
(agent_framework.channels.base) - reaproveita o contrato real em vez de
duplicar um dataclass equivalente. session_id do framework faz o papel de
conversation_id nesta PoC.
"""

from agent_framework.channels.base import ChannelMessage, ChannelResponse

Interaction = ChannelMessage

__all__ = ["ChannelMessage", "ChannelResponse", "Interaction"]
