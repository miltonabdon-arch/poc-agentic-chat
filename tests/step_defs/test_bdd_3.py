"""BDD — CRITERIOS-DE-ACEITE §3: perguntas respondidas com fonte RAG.

Responsabilidade: AI Developer Sr (Igor Scaglia)

Narrativa de colaboração:
  Ana entregou rag_pipeline/ (ingestão → Chroma, QueryResult).
  Gustavo entregou build_prompt() e not_found_response() (agent/prompt.py).
  Kirllen entregou normalize() e ChannelMessage (gateway/channel_gateway.py).
  O AI Dev Sr montou o grafo LangGraph que une esses contratos e
  escreveu estes cenários para validar o fluxo ponta a ponta por critério.

Steps compartilhados vêm de tests/step_defs/conftest.py.
"""

from pathlib import Path

from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

scenarios(str(_FEATURES / "criterios_3_rag.feature"))
