"""Channel Gateway — normaliza a requisição para ChannelMessage
usando ChannelGateway.normalize() nativo do agent_framework.

Canais suportados (embedded mode):
  "web"      → WebAdapter    (padrão — REST/Chainlit)
  "voice"    → VoiceAdapter  (URA/TIA — endpoint /agent/sse)
  "whatsapp" → WhatsAppAdapter
"""

import uuid
from datetime import datetime, timezone

from agent_framework.channels.base import ChannelMessage
from agent_framework.channels.gateway import ChannelGateway

_gateway = ChannelGateway(input_mode="embedded")


async def normalize(
    raw_message: str,
    conversation_id: str | None = None,
    canal: str = "web",
) -> ChannelMessage:
    payload = {
        "message": raw_message,
        "session_id": conversation_id or str(uuid.uuid4()),
        "channel_id": "tim-poc",
        "context": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }
    return await _gateway.normalize(canal, payload)
