"""Guardrail de output - equivalente simplificado de SPEC-005 (Guardrails).

Bloqueia citacao direta de concorrente por nome na resposta gerada pelo
agente, antes de entregar ao cliente.

Contrato (ver GuardrailResult em agent/models.py):
- Se a resposta citar o nome de um concorrente (lista fictícia, definida
  neste módulo), bloquear e retornar Violation.COMPETITOR_MENTION /
  Action.BLOCK com um texto substituto
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

import re

from agent.models import Action, GuardrailResult, Violation

# Lista fictícia de concorrentes para fins da PoC - não corresponde a
# nenhuma operadora real.
_COMPETITOR_NAMES = ["OperadoraZ", "TeleConecta", "FastMóvel"]

_COMPETITOR_RES = [
    re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    for name in _COMPETITOR_NAMES
]

# Mensagem neutra sem oferta de ajuda — evita loop de conversa na URA.
_BLOCK_MSG = "Essa informação não está disponível. Para saber mais sobre os planos da TIM, acesse o site oficial ou fale com um atendente."


def check_output(text: str) -> GuardrailResult:
    for pattern in _COMPETITOR_RES:
        if pattern.search(text):
            return GuardrailResult(
                guardrail_type="output",
                violation=Violation.COMPETITOR_MENTION,
                action_taken=Action.BLOCK,
                text=_BLOCK_MSG,
            )

    return GuardrailResult(
        guardrail_type="output",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=text,
    )
