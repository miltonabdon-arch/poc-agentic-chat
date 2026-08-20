"""BDD — CRITERIOS-DE-ACEITE §4: perguntas fora do catálogo não geram alucinação.

Filosofia "sem evidência, sem invenção":
  - rag_pipeline/query_api.py: threshold corta candidatos fracos (Ana).
  - agent/prompt.py: build_not_found_prompt() instrui o LLM a responder honestamente (Gustavo).
  - O grafo LangGraph chama o LLM com build_not_found_prompt() quando found=False (Igor).

Os cenários @unit patcham o LLM com o fragmento esperado ("Não encontrei essa informação"),
validando que o fluxo completo (RAG miss → build_not_found_prompt → LLM) produz a resposta correta.

Steps compartilhados vêm de tests/step_defs/conftest.py.
"""

from pathlib import Path

from pytest_bdd import scenarios

_FEATURES = Path(__file__).parent.parent / "features"

scenarios(str(_FEATURES / "criterios_4_fora_escopo.feature"))
