"""Channel Gateway (mock SSE) - equivalente simplificado de SPEC-009.

Normaliza uma requisicao de teste para o contrato Interaction. Simula, sem
implementar de fato, o formato do contrato SSE/TIA real (aguardando
"Adendo A" - ver integracao-sse-tia/spec.md no projeto principal).

TODO (Backend/Integração): implementar normalize() para satisfazer os
testes de tests/test_gateway.py.

Contrato (ver Interaction em gateway/models.py):
- conversation_id: usar o valor recebido, ou gerar um novo (ex.: uuid4) se
  não for fornecido
- channel: "mock_sse"
- timestamp: horário atual em UTC, formato ISO 8601
"""

import uuid
from datetime import datetime, timezone

from gateway.models import Interaction


def normalize(raw_message: str, conversation_id: str | None = None) -> Interaction:
    return Interaction(
        conversation_id=conversation_id or str(uuid.uuid4()),
        channel="mock_sse",
        message=raw_message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
