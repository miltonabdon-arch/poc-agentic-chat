"""Guardrail de output - equivalente simplificado de SPEC-005 (Guardrails).

Bloqueia citacao direta de concorrente por nome na resposta gerada pelo
agente, antes de entregar ao cliente.

TODO (AI Scientist / LLM Specialist): implementar check_output() para
satisfazer os testes de tests/test_agent.py.

Contrato (ver GuardrailResult em agent/models.py):
- Se a resposta citar o nome de um concorrente (lista fictícia, definida
  neste módulo), bloquear e retornar Violation.COMPETITOR_MENTION /
  Action.BLOCK com um texto substituto
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

from agent.models import GuardrailResult

# Lista fictícia de concorrentes para fins da PoC - não corresponde a
# nenhuma operadora real.
_COMPETITOR_NAMES = ["OperadoraZ", "TeleConecta", "FastMóvel"]


def check_output(text: str) -> GuardrailResult:
    raise NotImplementedError
