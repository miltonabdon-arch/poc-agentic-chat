"""Judge leve offline - equivalente simplificado de SPEC-006 (Evals).

Roda sobre um lote de interacoes ja registradas (nao bloqueia fluxo
sincrono) e sinaliza respostas sem source_document_id, um proxy simples
para possivel alucinacao. Nao substitui o Golden Standard Dataset do
projeto real (Deferred Idea em STATE.md) - e apenas uma checagem ilustrativa.

Contrato:
- interactions: lista de dict com chaves "interaction_id", "response",
  "source_document_id"
- Retorna uma lista de JudgeFinding, uma por interação, com flagged=True
  e um reason quando houver "response" mas nenhum "source_document_id"
"""

from dataclasses import dataclass


@dataclass
class JudgeFinding:
    interaction_id: str
    flagged: bool
    reason: str | None


def judge_batch(interactions: list[dict]) -> list[JudgeFinding]:
    findings = []
    for interaction in interactions:
        has_response = bool(interaction.get("response"))
        has_source = bool(interaction.get("source_document_id"))
        flagged = has_response and not has_source
        findings.append(
            JudgeFinding(
                interaction_id=interaction["interaction_id"],
                flagged=flagged,
                reason="resposta sem source_document_id (possível alucinação)" if flagged else None,
            )
        )
    return findings
