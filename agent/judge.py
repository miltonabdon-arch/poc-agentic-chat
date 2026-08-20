"""Judge leve offline - equivalente simplificado de SPEC-006 (Evals).

Roda sobre um lote de interacoes ja registradas (nao bloqueia fluxo
sincrono). Nao substitui o Golden Standard Dataset do projeto real
(Deferred Idea em STATE.md) - e apenas uma checagem ilustrativa com 7
proxies offline:

  1. empty_response       — resposta vazia ou em branco
  2. groundedness         — response sem source_document_id (possivel alucinacao)
  3. not_found_consistency — agente disse "nao encontrei" mas havia fonte
  4. length_anomaly       — response muito curta, possivel erro silencioso
  5. unwarranted_deflection — "consulte um atendente" quando havia fonte disponivel
  6. topic_coherence      — baixo overlap de keywords entre pergunta e resposta
  7. fabricated_data      — nomes proprios/valores monetarios sem fonte

Contrato:
- interactions: lista de dict com chaves:
    "interaction_id" (str)
    "question"       (str) — pergunta original do cliente
    "response"       (str) — resposta gerada pelo agente
    "source_document_id" (str | None) — ID do chunk RAG usado, ou None
    "guardrail_blocked"  (bool, opcional) — True se input_guardrail bloqueou
- Retorna lista de JudgeFinding, uma por interacao, com todos os problemas
  encontrados (lista vazia se passou em todos os checks).
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Padrões compilados
# ---------------------------------------------------------------------------

_NOT_FOUND_RE = re.compile(
    r"não encontrei"
    r"|não (tenho|possuo) (essa |esta |a )?informaç"
    r"|não (há|existe|tem) (essa |esta |a )?informaç"
    r"|não foi possível encontrar",
    re.IGNORECASE,
)

_DEFLECTION_RE = re.compile(
    r"consulte (um atendente|nossa central|o suporte)"
    r"|acesse o site oficial"
    r"|ligue para o \d+"
    r"|entre em contato com",
    re.IGNORECASE,
)

_MONEY_RE = re.compile(r"R\$\s?\d+[\.,]?\d*")
_PROPER_NAME_RE = re.compile(r"\b[A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+ [A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+\b")

# Stopwords para o check de coerência — palavras sem valor semântico
_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "e", "ou", "que", "se", "me", "por",
    "para", "com", "mais", "mas", "como", "ao", "à", "eu", "você", "meu",
    "minha", "qual", "quais", "tenho", "tem", "é", "são", "foi", "ser",
}

_MIN_RESPONSE_CHARS = 20
_MIN_TOPIC_OVERLAP = 0.15  # menos de 15% de overlap = suspeito


# ---------------------------------------------------------------------------
# Contrato de saída
# ---------------------------------------------------------------------------

@dataclass
class JudgeFinding:
    interaction_id: str
    flagged: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None


# ---------------------------------------------------------------------------
# Checks individuais
# ---------------------------------------------------------------------------

def _check_empty_response(interaction: dict) -> str | None:
    response = interaction.get("response")
    if not response or not response.strip():
        return "resposta vazia ou em branco — cliente sem atendimento"
    return None


def _check_groundedness(interaction: dict) -> str | None:
    response = interaction.get("response") or ""
    has_source = bool(interaction.get("source_document_id"))
    if response and not has_source and not _NOT_FOUND_RE.search(response):
        return "resposta gerada sem fonte RAG — possível alucinação"
    return None


def _check_not_found_consistency(interaction: dict) -> str | None:
    response = interaction.get("response") or ""
    has_source = bool(interaction.get("source_document_id"))
    if has_source and _NOT_FOUND_RE.search(response):
        return "agente disse 'não encontrei' mas havia fonte disponível"
    return None


def _check_length_anomaly(interaction: dict) -> str | None:
    response = interaction.get("response") or ""
    if response and len(response) < _MIN_RESPONSE_CHARS:
        return f"resposta muito curta ({len(response)} chars) — possível erro silencioso"
    return None


def _check_unwarranted_deflection(interaction: dict) -> str | None:
    """Detecta deflexão para atendente/site quando havia fonte RAG disponível."""
    response = interaction.get("response") or ""
    has_source = bool(interaction.get("source_document_id"))
    if has_source and _DEFLECTION_RE.search(response):
        return "agente redirecionou para atendente/site mesmo tendo fonte disponível"
    return None


def _check_topic_coherence(interaction: dict) -> str | None:
    """Verifica se a resposta tem overlap mínimo de keywords com a pergunta."""
    question = interaction.get("question") or ""
    response = interaction.get("response") or ""
    if not question or not response:
        return None

    def keywords(text: str) -> set[str]:
        tokens = re.findall(r"[a-záéíóúãõâêôç]+", text.lower())
        return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}

    q_kws = keywords(question)
    r_kws = keywords(response)
    if not q_kws:
        return None

    overlap = len(q_kws & r_kws) / len(q_kws)
    if overlap < _MIN_TOPIC_OVERLAP:
        return (
            f"baixo overlap de tópicos entre pergunta e resposta "
            f"({overlap:.0%}) — possível roteamento errado"
        )
    return None


def _check_fabricated_data(interaction: dict) -> str | None:
    """Detecta nomes próprios ou valores monetários na resposta sem fonte RAG."""
    response = interaction.get("response") or ""
    has_source = bool(interaction.get("source_document_id"))
    if has_source or not response:
        return None

    has_money = bool(_MONEY_RE.search(response))
    has_name = bool(_PROPER_NAME_RE.search(response))
    if has_money or has_name:
        fabricated = []
        if has_name:
            fabricated.append("nomes próprios")
        if has_money:
            fabricated.append("valores monetários")
        return f"resposta cita {' e '.join(fabricated)} sem fonte — possível dado fabricado"
    return None


_CHECKS = [
    _check_empty_response,
    _check_groundedness,
    _check_not_found_consistency,
    _check_length_anomaly,
    _check_unwarranted_deflection,
    _check_topic_coherence,
    _check_fabricated_data,
]


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def judge_batch(interactions: list[dict]) -> list[JudgeFinding]:
    """Avalia um lote de interações e retorna um JudgeFinding por interação.

    Diferente da versão anterior, acumula TODOS os problemas encontrados
    (não para no primeiro). Use finding.flagged para filtrar e
    finding.reasons para ver todos os motivos.
    """
    findings = []
    for interaction in interactions:
        iid = interaction.get("interaction_id", "unknown")
        reasons = [r for check in _CHECKS if (r := check(interaction)) is not None]
        findings.append(JudgeFinding(
            interaction_id=iid,
            flagged=bool(reasons),
            reasons=reasons,
        ))
    return findings
