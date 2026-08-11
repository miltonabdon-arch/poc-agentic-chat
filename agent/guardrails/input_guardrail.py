"""Guardrail de input - equivalente simplificado de SPEC-005 (Guardrails).

Mascara PII (CPF) e bloqueia perguntas fora do dominio do catalogo de
planos/ofertas, antes de qualquer chamada ao LLM.

TODO (AI Scientist / LLM Specialist): implementar check_input() para
satisfazer os testes de tests/test_agent.py.

Contrato (ver GuardrailResult em agent/models.py):
- Se o texto contiver um CPF (com ou sem pontuação), mascarar e retornar
  Violation.PII / Action.MASK com o texto mascarado
- Se o texto pedir dados pessoais de terceiros (ex.: "CPF de um cliente"),
  bloquear e retornar Violation.OUT_OF_DOMAIN / Action.BLOCK
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

from agent.models import GuardrailResult


def check_input(text: str) -> GuardrailResult:
    raise NotImplementedError
