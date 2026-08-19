"""BDD — CRITERIOS-DE-ACEITE §6: traço de observabilidade legível e rastreável.

O traço é emitido em duas camadas por orchestrator/tracer.py (AI Dev Sr):
  1. AgentObserver (agent_framework): noop local, real em OCI.
  2. Log estruturado local: TRACE|type|campo=valor — grep-friendly.

O sumário final (TRACE|SUMARIO) é gerado por log_sumario_interacao() ao
fim de run_interaction(), após o grafo terminar. Contém latencia_ms,
chunk_id e a lista de guardrails acionados.

Os cenários @unit verificam o traço capturando caplog (fixture de conftest).

Steps compartilhados vêm de tests/step_defs/conftest.py.
"""

from pathlib import Path

from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

scenarios(str(_FEATURES / "criterios_6_observabilidade.feature"))
