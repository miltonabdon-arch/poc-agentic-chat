"""Guardrail de output - bloqueia citacao direta de concorrente por nome.

O framework agent_framework.guardrails nao expoe um rail pronto para
"mencao a concorrente" (os rails de output reais - ComplianceRail,
ProactiveOfferRail, OutputPiiMaskRail - cobrem outros escopos, ver
agent_framework.guardrails.rails) - esta checagem determinística com a
lista ficticia de concorrentes desta PoC preenche esse gap específico.

Contrato (ver GuardrailResult em agent/models.py):
- Se a resposta citar o nome de um concorrente (lista fictícia, definida
  neste módulo), bloquear e retornar Violation.COMPETITOR_MENTION /
  Action.BLOCK com um texto substituto
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

from agent.models import Action, GuardrailResult, Violation

# Lista fictícia de concorrentes para fins da PoC - não corresponde a
# nenhuma operadora real.
_COMPETITOR_NAMES = ["OperadoraZ", "TeleConecta", "FastMóvel"]


def check_output(text: str) -> GuardrailResult:
    for name in _COMPETITOR_NAMES:
        if name.lower() in (text or "").lower():
            return GuardrailResult(
                guardrail_type="output",
                violation=Violation.COMPETITOR_MENTION,
                action_taken=Action.BLOCK,
                text="Não posso comparar nossos planos com o de outras operadoras.",
            )

    return GuardrailResult(
        guardrail_type="output",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=text,
    )
