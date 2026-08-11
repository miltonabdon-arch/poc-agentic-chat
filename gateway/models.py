"""Contrato Interaction - ver docs/ARQUITETURA.md."""

from dataclasses import dataclass


@dataclass
class Interaction:
    conversation_id: str
    channel: str  # "mock_sse"
    message: str
    timestamp: str
