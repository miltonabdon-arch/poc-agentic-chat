"""BDD — CRITERIOS-DE-ACEITE §4: perguntas fora do catálogo não geram alucinação.

Filosofia "sem evidência, sem invenção":
  - rag_pipeline/query_api.py: threshold corta candidatos fracos (Ana).
  - agent/prompt.py: build_prompt() retorna None → not_found_response() (Gustavo).
  - O grafo LangGraph propaga essa decisão sem chamar o LLM (Igor).

Os cenários @unit patcham o LLM, mas para perguntas fora do catálogo o LLM
nunca é chamado (not_found_response() é retornado antes) — o mock é inócuo.
Isso valida que o pipeline respeita a decisão de not_found_response().

Steps compartilhados vêm de tests/step_defs/conftest.py.
"""

from pathlib import Path

from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

scenarios(str(_FEATURES / "criterios_4_fora_escopo.feature"))
