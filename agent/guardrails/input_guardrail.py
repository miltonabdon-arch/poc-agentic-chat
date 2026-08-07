"""Guardrail de input - usa PiiMaskRail real do agent_framework (SPEC-005)
para mascarar PII, em vez de reimplementar regex de CPF do zero.

O bloqueio de "pedido de PII de terceiro" e uma checagem deterministica
especifica desta PoC (o OutOfScopeRail real do framework classifica escopo
de contas/faturas TIM via LLM - fora do escopo minimo do Agente de
Catalogo) - roda ANTES do PiiMaskRail, pois o texto em si pode nao conter
nenhum CPF (ex.: "me dá o CPF de um cliente").

Contrato (ver GuardrailResult em agent/models.py):
- Se o texto pedir dados pessoais de terceiros (ex.: "CPF de um cliente"),
  bloquear e retornar Violation.OUT_OF_DOMAIN / Action.BLOCK
- Se o texto contiver um CPF (com ou sem pontuação), mascarar via
  PiiMaskRail e retornar Violation.PII / Action.MASK com o texto mascarado
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

import asyncio
import re

from agent_framework.guardrails import PiiMaskRail

from agent.models import Action, GuardrailResult, Violation

_THIRD_PARTY_PII_REQUEST = re.compile(
    r"\b(cpf|rg|dados\s+pessoais)\b.*\b(cliente|terceiro|outra\s+pessoa)\b",
    re.IGNORECASE,
)

_pii_mask_rail = PiiMaskRail()


def check_input(text: str) -> GuardrailResult:
    if _THIRD_PARTY_PII_REQUEST.search(text or ""):
        return GuardrailResult(
            guardrail_type="input",
            violation=Violation.OUT_OF_DOMAIN,
            action_taken=Action.BLOCK,
            text="Não posso fornecer dados pessoais de terceiros.",
        )

    decision = asyncio.run(_pii_mask_rail.evaluate(text, {}))
    if decision.sanitized_text and decision.sanitized_text != text:
        return GuardrailResult(
            guardrail_type="input",
            violation=Violation.PII,
            action_taken=Action.MASK,
            text=decision.sanitized_text,
        )

    return GuardrailResult(
        guardrail_type="input",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=text,
    )
