"""BDD — CRITERIOS-DE-ACEITE §5: guardrails de input e output ativos.

Os cenários @unit testam os guardrails em dois níveis:
  1. Isolado: check_input()/check_output() diretamente — máxima precisão de diagnóstico.
  2. Pipeline (apenas @live_llm): PII não deve vazar na resposta final mesmo com LLM real.

A separação limpa entre os dois níveis é intencional:
  - Isolado: todo defeito no guardrail é imediatamente localizável.
  - Pipeline: valida que o grafo (AI Dev Sr) aplica o guardrail no nó correto.

Steps compartilhados (guardrail) vêm de tests/step_defs/conftest.py.
"""

from pathlib import Path

from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

scenarios(str(_FEATURES / "criterios_5_guardrails.feature"))
