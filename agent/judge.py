"""Judge leve offline - equivalente simplificado de SPEC-006 (Evals).

Roda sobre um lote de interacoes ja registradas (nao bloqueia fluxo
sincrono) e sinaliza respostas sem source_document_id, um proxy simples
para possivel alucinacao. Nao substitui o Golden Standard Dataset do
projeto real (Deferred Idea em STATE.md) - e apenas uma checagem ilustrativa.

TODO (AI Scientist / LLM Specialist): implementar judge_batch().

Contrato:
- interactions: lista de dict com chaves "interaction_id", "response",
  "source_document_id"
- Retornar uma lista de JudgeFinding, uma por interação, com flagged=True
  e um reason quando houver "response" mas nenhum "source_document_id"
"""

from dataclasses import dataclass


@dataclass
class JudgeFinding:
    interaction_id: str
    flagged: bool
    reason: str | None


def judge_batch(interactions: list[dict]) -> list[JudgeFinding]:
    raise NotImplementedError
