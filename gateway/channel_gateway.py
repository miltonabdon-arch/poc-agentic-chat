"""Channel Gateway (mock SSE) - usa ChannelMessage real do agent_framework
(agent_framework.channels.base) via gateway/models.py.

Normaliza uma requisicao de teste para o contrato ChannelMessage do
framework. Simula, sem implementar o contrato SSE/TIA real (aguardando
"Adendo A" - ver integracao-sse-tia/spec.md no projeto principal), o canal
"mock_sse" desta PoC.

Contrato (ver Interaction = ChannelMessage em gateway/models.py):
- session_id: usar o valor recebido, ou gerar um novo (uuid4) se não
  fornecido - faz o papel de conversation_id nesta PoC
- channel: "mock_sse"
- text: o texto recebido
"""

import uuid

from gateway.models import Interaction


def normalize(raw_message: str, conversation_id: str | None = None) -> Interaction:
    return Interaction(
        channel="mock_sse",
        session_id=conversation_id or str(uuid.uuid4()),
        text=raw_message,
    )
