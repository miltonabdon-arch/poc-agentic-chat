"""Guardrail de output - equivalente simplificado de SPEC-005 (Guardrails).

Filtra a resposta gerada pelo agente antes de entregar ao cliente.
Quatro verificações, em ordem de severidade:

  1. CONTEXT_LEAK       — seções internas do prompt vazaram na resposta (BLOCK)
  2. DOWNGRADE_PROPOSAL — proposta de plano menor detectada na jornada de Informação (BLOCK)
  3. COMPETITOR_MENTION — nome de concorrente citado diretamente (MASK inline)
  4. FORMAT_VIOLATION   — markdown residual em canal de voz (MASK/limpeza)

Contrato (ver GuardrailResult em agent/models.py):
- CONTEXT_LEAK       → Action.BLOCK  — resposta substituída por mensagem neutra
- DOWNGRADE_PROPOSAL → Action.BLOCK  — resposta substituída quando intent=="informacao"
- COMPETITOR         → Action.MASK   — nome substituído inline por "outra operadora"
- FORMAT             → Action.MASK   — marcadores markdown removidos
- Nenhuma            → Action.ALLOW  — texto original passado sem alteração
"""

import re

from agent.models import Action, GuardrailResult, Violation

# Concorrentes reais + nomes fictícios usados nos testes BDD.
_COMPETITOR_NAMES = ["Claro", "Vivo", "Oi", "Net", "OperadoraZ", "TeleConecta", "FastMóvel"]
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

def _clean_markdown(text: str) -> str:
    """Remove formatação markdown preservando o conteúdo textual para voz.

    Cada tipo é tratado separadamente para garantir que apenas os delimitadores
    sejam removidos — o texto falado não pode perder informação.
    """
    # Negrito/itálico: **TIM Turbo** → TIM Turbo  (nunca remove o nome)
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    # Cabeçalhos: ## Planos → Planos
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Marcadores de lista: - Item → Item
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Links: [site da TIM](https://...) → site da TIM  (URL não pode ser lida em voz)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Código inline/bloco: `valor` → valor
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    return text.strip()

# Padrões de proposta de downgrade — bloqueados quando a jornada é "informacao"
# (o catálogo RAG deve informar, não sugerir troca para plano inferior).
_DOWNGRADE_RE = re.compile(
    r"(plano\s+mais\s+barato|plano\s+menor|reduzir\s+(seu\s+)?plano|"
    r"plano\s+inferior|plano\s+econ[oô]mico|"
    r"trocar\s+para\s+um\s+plano\s+mais\s+barato|downgrade)",
    re.IGNORECASE,
)

_BLOCK_MSG = (
    "Essa informação não está disponível. "
    "Para saber mais sobre os planos da TIM, acesse o site oficial ou fale com um atendente."
)

_DOWNGRADE_BLOCK_MSG = (
    "Posso ajudar com informações sobre planos e benefícios da TIM. "
    "Para simular mudanças de plano, me informe qual plano você tem interesse."
)


def check_output(text: str, intent: str | None = None) -> GuardrailResult:
    # 1. Vazamento de contexto interno — mais grave, bloqueia tudo
    for pattern in _CONTEXT_LEAK_RES:
        if pattern.search(text):
            return GuardrailResult(
                guardrail_type="output",
                violation=Violation.CONTEXT_LEAK,
                action_taken=Action.BLOCK,
                text=_BLOCK_MSG,
            )

    # 2. Proposta de downgrade na jornada de Informação — a jornada de catálogo
    # deve informar, não redirecionar o cliente para planos mais baratos.
    if intent == "informacao" and _DOWNGRADE_RE.search(text):
        return GuardrailResult(
            guardrail_type="output",
            violation=Violation.DOWNGRADE_PROPOSAL,
            action_taken=Action.BLOCK,
            text=_DOWNGRADE_BLOCK_MSG,
        )

    # 3. Citação de concorrente — substitui inline (preserva o restante da resposta)
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

    # 4. Markdown residual — limpa preservando conteúdo para voz
    cleaned = _clean_markdown(text)
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
