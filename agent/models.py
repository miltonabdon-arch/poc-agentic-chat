"""Contratos de dados do agente - ver docs/ARQUITETURA.md."""

from dataclasses import dataclass
from enum import Enum


class Violation(str, Enum):
    PII = "pii"
    COMPETITOR_MENTION = "competitor_mention"
    OUT_OF_DOMAIN = "out_of_domain"
    NONE = "none"


class Action(str, Enum):
    BLOCK = "block"
    MASK = "mask"
    ALLOW = "allow"


@dataclass
class GuardrailResult:
    guardrail_type: str  # "input" | "output"
    violation: Violation
    action_taken: Action
    text: str  # texto resultante (mascarado, ou original se allow)
