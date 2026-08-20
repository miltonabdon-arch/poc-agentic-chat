"""Judge offline — alinhado com agent_framework.judges.judge.JudgePipeline.

Usa JudgePipeline (stub local com mesma interface do framework real) lendo
config/judges.yaml. Judges do framework:
  - GroundednessJudge    → overlap de evidência na resposta
  - ResponseQualityJudge → tamanho mínimo

Extensões customizadas desta PoC (não existem no framework):
  - NotFoundConsistencyJudge  — disse "não encontrei" mas havia fonte
  - UnwarrantedDeflectionJudge — redirecionou para atendente com fonte disponível
  - TopicCoherenceJudge       — baixo overlap de keywords entre pergunta e resposta
  - FabricatedDataJudge       — nomes próprios ou valores sem fonte

Interface pública:
  evaluate_all(question, answer, context) -> list[JudgeResult]

Contexto esperado (dict):
  "source_document_id" (str | None)
  "evidence"           (str | None) — texto do chunk RAG usado
"""

from __future__ import annotations

import re

from agent_framework.judges.judge import (
    BaseJudge,
    JudgePipeline,
    JudgeResult,
)

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
_PROPER_NAME_RE = re.compile(
    r"\b[A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+ [A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+\b"
)

_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "e", "ou", "que", "se", "me", "por",
    "para", "com", "mais", "mas", "como", "ao", "à", "eu", "você", "meu",
    "minha", "qual", "quais", "tenho", "tem", "é", "são", "foi", "ser",
}

_MIN_TOPIC_OVERLAP = 0.15


# ---------------------------------------------------------------------------
# Extensões customizadas da PoC
# ---------------------------------------------------------------------------

class NotFoundConsistencyJudge(BaseJudge):
    name = "not_found_consistency"
    threshold = 1.0

    def evaluate(self, question: str, answer: str, context: dict) -> JudgeResult:
        has_source = bool(context.get("source_document_id"))
        if has_source and _NOT_FOUND_RE.search(answer):
            return JudgeResult(
                name=self.name, score=0.0, passed=False,
                reason="agente disse 'não encontrei' mas havia fonte disponível",
            )
        return JudgeResult(name=self.name, score=1.0, passed=True)


class UnwarrantedDeflectionJudge(BaseJudge):
    name = "unwarranted_deflection"
    threshold = 1.0

    def evaluate(self, question: str, answer: str, context: dict) -> JudgeResult:
        has_source = bool(context.get("source_document_id"))
        if has_source and _DEFLECTION_RE.search(answer):
            return JudgeResult(
                name=self.name, score=0.0, passed=False,
                reason="agente redirecionou para atendente/site mesmo tendo fonte disponível",
            )
        return JudgeResult(name=self.name, score=1.0, passed=True)


class TopicCoherenceJudge(BaseJudge):
    name = "topic_coherence"
    threshold = _MIN_TOPIC_OVERLAP

    def evaluate(self, question: str, answer: str, context: dict) -> JudgeResult:
        if not question or not answer:
            return JudgeResult(name=self.name, score=1.0, passed=True)

        def keywords(text: str) -> set[str]:
            tokens = re.findall(r"[a-záéíóúãõâêôç]+", text.lower())
            return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}

        q_kws = keywords(question)
        if not q_kws:
            return JudgeResult(name=self.name, score=1.0, passed=True)

        overlap = len(q_kws & keywords(answer)) / len(q_kws)
        passed = overlap >= self.threshold
        return JudgeResult(
            name=self.name,
            score=round(overlap, 3),
            passed=passed,
            reason="" if passed else (
                f"baixo overlap de tópicos entre pergunta e resposta ({overlap:.0%})"
                " — possível roteamento errado"
            ),
        )


class FabricatedDataJudge(BaseJudge):
    name = "fabricated_data"
    threshold = 1.0

    def evaluate(self, question: str, answer: str, context: dict) -> JudgeResult:
        has_source = bool(context.get("source_document_id"))
        if has_source or not answer:
            return JudgeResult(name=self.name, score=1.0, passed=True)

        fabricated = []
        if _PROPER_NAME_RE.search(answer):
            fabricated.append("nomes próprios")
        if _MONEY_RE.search(answer):
            fabricated.append("valores monetários")

        if fabricated:
            return JudgeResult(
                name=self.name, score=0.0, passed=False,
                reason=f"resposta cita {' e '.join(fabricated)} sem fonte — possível dado fabricado",
            )
        return JudgeResult(name=self.name, score=1.0, passed=True)


# ---------------------------------------------------------------------------
# Pipeline principal — lê config/judges.yaml + injeta extensões customizadas
# ---------------------------------------------------------------------------

_CUSTOM_JUDGES: list[BaseJudge] = [
    NotFoundConsistencyJudge(),
    UnwarrantedDeflectionJudge(),
    TopicCoherenceJudge(),
    FabricatedDataJudge(),
]

pipeline = JudgePipeline(
    config_path="config/judges.yaml",
    custom_judges=_CUSTOM_JUDGES,
)


async def evaluate_all(
    question: str,
    answer: str,
    context: dict | None = None,
) -> list[JudgeResult]:
    """Interface pública — equivalente a JudgePipeline.evaluate_all() do framework."""
    return await pipeline.evaluate_all(question, answer, context or {})
