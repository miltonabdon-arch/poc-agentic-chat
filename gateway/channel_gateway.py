"""Channel Gateway (mock SSE) — normaliza a requisição para ChannelMessage
do agent_framework (contrato nativo), simulando o canal SSE/TIA real.
"""

import uuid
from datetime import datetime, timezone

from agent_framework.channels.base import ChannelMessage


def normalize(raw_message: str, conversation_id: str | None = None) -> ChannelMessage:
    return ChannelMessage(
        channel="mock_sse",
        channel_id="tim-poc",
        session_id=conversation_id or str(uuid.uuid4()),
        user_id="anonymous",
        text=raw_message,
        context={"timestamp": datetime.now(timezone.utc).isoformat()},
    )
