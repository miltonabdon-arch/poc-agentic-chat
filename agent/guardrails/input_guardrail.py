"""Guardrail de input — wrapper sobre GuardrailPipeline do agent_framework.

Ordem: ToxicityRail (block) → OutOfScopeRail (block) → PiiMaskRail (sanitize).
Adapta RailDecision → GuardrailResult para o orquestrador (graph.py) não mudar.
"""

from agent_framework.guardrails import GuardrailPipeline
from agent_framework.guardrails.rail import RailAction
from agent_framework.guardrails.rails import OutOfScopeRail, PiiMaskRail, ToxicityRail

from agent.models import Action, GuardrailResult, Violation

_pipeline = GuardrailPipeline(rails=[ToxicityRail(), OutOfScopeRail(), PiiMaskRail()])

_VIOLATION_MAP = {
    "toxicity": Violation.TOXICITY,
    "out_of_domain": Violation.OUT_OF_DOMAIN,
    "pii": Violation.PII,
}
_ACTION_MAP = {
    RailAction.allow: Action.ALLOW,
    RailAction.sanitize: Action.MASK,
    RailAction.block: Action.BLOCK,
}


def check_input(text: str) -> GuardrailResult:
    decisions = _pipeline.run(text)

    for d in decisions:
        if d.action != RailAction.allow:
            violation = _VIOLATION_MAP.get(
                d.metadata.get("violation", ""), Violation.NONE
            )
            return GuardrailResult(
                guardrail_type="input",
                violation=violation,
                action_taken=_ACTION_MAP.get(d.action, Action.ALLOW),
                text=d.text,
            )

    final_text = decisions[-1].text if decisions else text
    return GuardrailResult(
        guardrail_type="input",
        violation=Violation.NONE,
        action_taken=Action.ALLOW,
        text=final_text,
    )
