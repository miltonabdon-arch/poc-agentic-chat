"""Judge leve offline - equivalente simplificado de SPEC-006 (Evals).

Roda sobre um lote de interacoes ja registradas (nao bloqueia fluxo
sincrono). Nao substitui o Golden Standard Dataset do projeto real
(Deferred Idea em STATE.md) - e apenas uma checagem ilustrativa com 3
proxies offline:

  1. groundedness   — response sem source_document_id (possivel alucinacao)
  2. not_found_consistency — agente disse "nao encontrei" mas havia fonte
  3. length_anomaly — response muito curta, possivel erro silencioso

Contrato:
- interactions: lista de dict com chaves "interaction_id", "response",
  "source_document_id"
- Retorna uma lista de JudgeFinding, uma por interação, com o primeiro
  problema encontrado (ou flagged=False se passou em todos os checks)
"""

import re
from dataclasses import dataclass

_NOT_FOUND_RE = re.compile(
    r"não encontrei"
    r"|não (tenho|possuo) (essa |esta |a )?informaç"
    r"|não (há|existe|tem) (essa |esta |a )?informaç"
    r"|não foi possível encontrar",
    re.IGNORECASE,
)

# Respostas menores que isso são suspeitas de erro silencioso.
_MIN_RESPONSE_CHARS = 20


@dataclass
class JudgeFinding:
    interaction_id: str
    flagged: bool
    reason: str | None


def _check_groundedness(interaction: dict) -> str | None:
    if interaction.get("response") and not interaction.get("source_document_id"):
        return "response sem fonte — possível alucinação"
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


_CHECKS = [
    _check_groundedness,
    _check_not_found_consistency,
    _check_length_anomaly,
]


def judge_batch(interactions: list[dict]) -> list[JudgeFinding]:
    findings = []
    for interaction in interactions:
        iid = interaction.get("interaction_id", "unknown")
        reason = next(
            (r for check in _CHECKS if (r := check(interaction)) is not None),
            None,
        )
        findings.append(JudgeFinding(
            interaction_id=iid,
            flagged=reason is not None,
            reason=reason,
        ))
    return findings
