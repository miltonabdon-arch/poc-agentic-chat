"""Guardrail de input - equivalente simplificado de SPEC-005 (Guardrails).

Mascara PII (CPF, CNPJ, e-mail, telefone) e bloqueia perguntas fora do
domínio do catálogo de planos/ofertas, antes de qualquer chamada ao LLM.

Contrato (ver GuardrailResult em agent/models.py):
- Se o texto pedir dados pessoais de terceiros, bloquear (OUT_OF_DOMAIN / BLOCK).
  text retorna o original — o orquestrador descarta, mas fica disponível para auditoria.
- Se o texto contiver PII (CPF, CNPJ, e-mail ou telefone), mascarar toda
  ocorrência em cadeia e retornar Violation.PII / Action.MASK.
- Caso contrário, retornar Violation.NONE / Action.ALLOW com o texto original.

Ordem de verificação: OUT_OF_DOMAIN antes de PII — evitar mascarar antes de
detectar que a pergunta inteira deve ser bloqueada.
"""

import re

from agent.models import Action, GuardrailResult, Violation

# --- PII patterns -----------------------------------------------------------

_CPF_RE = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_CNPJ_RE = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}[/]?\d{4}-?\d{2}(?!\d)")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?55[\s\-]?)?"       # código de país opcional
    r"\(?\d{2}\)?\s?"          # DDD obrigatório (reduz falsos positivos)
    r"9?\d{4}[\s\-]?\d{4}"    # número: 8 ou 9 dígitos
    r"(?!\d)"
)

_PII_RULES: list[tuple[re.Pattern, str]] = [
    (_CNPJ_RE, "**.***.****/****-**"),
    (_CPF_RE,  "***.***.***-**"),
    (_EMAIL_RE, "***@***.***"),
    (_PHONE_RE, "(**) *****-****"),
]

# --- Out-of-domain patterns -------------------------------------------------

_OUT_OF_DOMAIN_PATTERNS = [
    re.compile(r"\bcpf\b.*\b(cliente|usu[aá]rio|pessoa|outro)\b", re.IGNORECASE),
    re.compile(r"\b(cliente|usu[aá]rio|pessoa|outro)\b.*\bcpf\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------


def check_input(text: str) -> GuardrailResult:
    # 1. Bloqueia perguntas fora do domínio antes de qualquer mascaramento
    for pattern in _OUT_OF_DOMAIN_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(
                guardrail_type="input",
                violation=Violation.OUT_OF_DOMAIN,
                action_taken=Action.BLOCK,
                text=text,  # original preservado para auditoria
            )

    # 2. Mascara toda PII encontrada, em cadeia (uma passagem por tipo)
    masked = text
    found_pii = False
    for pii_re, replacement in _PII_RULES:
        new = pii_re.sub(replacement, masked)
        if new != masked:
            found_pii = True
            masked = new

    if found_pii:
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
