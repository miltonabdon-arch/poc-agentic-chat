"""Guardrail de input - equivalente simplificado de SPEC-005 (Guardrails).

Mascara PII (CPF) e bloqueia perguntas fora do dominio do catalogo de
planos/ofertas, antes de qualquer chamada ao LLM.

Contrato (ver GuardrailResult em agent/models.py):
- Se o texto contiver um CPF (com ou sem pontuação), mascarar e retornar
  Violation.PII / Action.MASK com o texto mascarado
- Se o texto pedir dados pessoais de terceiros (ex.: "CPF de um cliente"),
  bloquear e retornar Violation.OUT_OF_DOMAIN / Action.BLOCK
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto
  original
"""

import re

from agent.models import Action, GuardrailResult, Violation

_CPF_RE = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")

_OUT_OF_DOMAIN_PATTERNS = [
    re.compile(r"\bcpf\b.*\b(cliente|usu[aá]rio|pessoa|outro)\b", re.IGNORECASE),
    re.compile(r"\b(cliente|usu[aá]rio|pessoa|outro)\b.*\bcpf\b", re.IGNORECASE),
]


def check_input(text: str) -> GuardrailResult:
    for pattern in _OUT_OF_DOMAIN_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(
                guardrail_type="input",
                violation=Violation.OUT_OF_DOMAIN,
                action_taken=Action.BLOCK,
                text="",
            )

    if _CPF_RE.search(text):
        masked = _CPF_RE.sub("***.***.***-**", text)
        return GuardrailResult(
            guardrail_type="input",
            violation=Violation.PII,
            action_taken=Action.MASK,
            text=masked,
        )

    return GuardrailResult(
        guardrail_type="input",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=text,
    )
