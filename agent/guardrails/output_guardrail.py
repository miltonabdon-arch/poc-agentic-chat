"""Guardrail de output - equivalente simplificado de SPEC-005 (Guardrails).

Filtra a resposta gerada pelo agente antes de entregar ao cliente.
Três verificações, em ordem de severidade:

  1. CONTEXT_LEAK   — seções internas do prompt vazaram na resposta (BLOCK)
  2. COMPETITOR_MENTION — nome de concorrente citado diretamente (MASK inline)
  3. FORMAT_VIOLATION   — markdown residual em canal de voz (MASK/limpeza)

Contrato (ver GuardrailResult em agent/models.py):
- CONTEXT_LEAK  → Action.BLOCK  — resposta inteira substituída por mensagem neutra
- COMPETITOR    → Action.MASK   — nome substituído inline por "outra operadora"
- FORMAT        → Action.MASK   — marcadores markdown removidos
- Nenhuma       → Action.ALLOW  — texto original passado sem alteração
"""

import re

from agent.models import Action, GuardrailResult, Violation

# Lista fictícia de concorrentes para fins da PoC.
_COMPETITOR_NAMES = ["OperadoraZ", "TeleConecta", "FastMóvel"]
_COMPETITOR_RES = [
    re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    for name in _COMPETITOR_NAMES
]
_COMPETITOR_SUBSTITUTE = "outra operadora"

# Padrões que indicam que seções internas do prompt vazaram para a resposta.
_CONTEXT_LEAK_RES = [
    re.compile(r"\[fonte interno", re.IGNORECASE),
    re.compile(r"\[CONTEXTO\]", re.IGNORECASE),
    re.compile(r"\[HISTÓRICO\]", re.IGNORECASE),
    re.compile(r"\[FERRAMENTAS DISPONÍVEIS\]", re.IGNORECASE),
    re.compile(r"\[PERGUNTA DO CLIENTE\]", re.IGNORECASE),
]

# Markdown que não deve aparecer em respostas de voz.
_MARKDOWN_RE = re.compile(
    r"\*{1,3}[^*]+\*{1,3}"       # negrito/itálico: **texto** ou *texto*
    r"|#{1,6}\s"                  # cabeçalhos: ## Título
    r"|^\s*[-*+]\s"               # listas com marcador
    r"|\[.*?\]\(.*?\)"            # links: [texto](url)
    r"|`{1,3}[^`]*`{1,3}",       # código inline ou bloco
    re.MULTILINE,
)

_BLOCK_MSG = (
    "Essa informação não está disponível. "
    "Para saber mais sobre os planos da TIM, acesse o site oficial ou fale com um atendente."
)


def check_output(text: str) -> GuardrailResult:
    # 1. Vazamento de contexto interno — mais grave, bloqueia tudo
    for pattern in _CONTEXT_LEAK_RES:
        if pattern.search(text):
            return GuardrailResult(
                guardrail_type="output",
                violation=Violation.CONTEXT_LEAK,
                action_taken=Action.BLOCK,
                text=_BLOCK_MSG,
            )

    # 2. Citação de concorrente — substitui inline (preserva o restante da resposta)
    masked = text
    for pattern in _COMPETITOR_RES:
        masked = pattern.sub(_COMPETITOR_SUBSTITUTE, masked)
    if masked != text:
        return GuardrailResult(
            guardrail_type="output",
            violation=Violation.COMPETITOR_MENTION,
            action_taken=Action.MASK,
            text=masked,
        )

    # 3. Markdown residual — limpa e entrega
    cleaned = _MARKDOWN_RE.sub("", text).strip()
    if cleaned != text:
        return GuardrailResult(
            guardrail_type="output",
            violation=Violation.FORMAT_VIOLATION,
            action_taken=Action.MASK,
            text=cleaned,
        )

    return GuardrailResult(
        guardrail_type="output",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=text,
    )
