"""Guardrail de output — wrapper sobre GuardrailPipeline do agent_framework.

Ordem: ContextLeakRail (block) → DowngradeProposalRail (block, se intent==informacao)
       → CompetitorMaskRail (sanitize) → MarkdownCleanRail (sanitize).
Adapta RailDecision → GuardrailResult para o orquestrador (graph.py) não mudar.
"""

from agent_framework.guardrails import GuardrailPipeline
from agent_framework.guardrails.rail import RailAction
from agent_framework.guardrails.rails import (
    CompetitorMaskRail,
    ContextLeakRail,
    DowngradeProposalRail,
    MarkdownCleanRail,
)

from agent.models import Action, GuardrailResult, Violation

_VIOLATION_MAP = {
    "context_leak": Violation.CONTEXT_LEAK,
    "downgrade_proposal": Violation.DOWNGRADE_PROPOSAL,
    "competitor_mention": Violation.COMPETITOR_MENTION,
    "format_violation": Violation.FORMAT_VIOLATION,
}
_ACTION_MAP = {
    RailAction.allow: Action.ALLOW,
    RailAction.sanitize: Action.MASK,
    RailAction.block: Action.BLOCK,
}


def check_output(text: str, intent: str | None = None) -> GuardrailResult:
    pipeline = GuardrailPipeline(rails=[
        ContextLeakRail(),
        DowngradeProposalRail(intent=intent),
        CompetitorMaskRail(),
        MarkdownCleanRail(),
    ])
    decisions = pipeline.run(text)

    blocking = next((d for d in decisions if d.action == RailAction.block), None)
    if blocking:
        violation = _VIOLATION_MAP.get(
            blocking.metadata.get("violation", ""), Violation.NONE
        )
        return GuardrailResult(
            guardrail_type="output",
            violation=violation,
            action_taken=Action.BLOCK,
            text=blocking.text,
        )

    sanitized = next((d for d in decisions if d.action == RailAction.sanitize), None)
    if sanitized:
        violation = _VIOLATION_MAP.get(
            sanitized.metadata.get("violation", ""), Violation.NONE
        )
        final_text = decisions[-1].text
        return GuardrailResult(
            guardrail_type="output",
            violation=violation,
            action_taken=Action.MASK,
            text=final_text,
        )

    return GuardrailResult(
        guardrail_type="output",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=decisions[-1].text if decisions else text,
    )
