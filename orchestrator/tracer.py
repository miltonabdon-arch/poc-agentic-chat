"""Observability Tracer - equivalente simplificado de SPEC-007.

Deve registrar cada interacao via OpenTelemetry local, exportado para
console. Substitui, para os fins desta PoC, o Langfuse+OpenTelemetry+eventos
IC/NOC/GRL gerenciados do framework real (ver docs/ARQUITETURA.md).

TODO (AI Developer Sr): implementar trace_interaction() como um context
manager que:
- Abre um span OpenTelemetry por interação (conversation_id como atributo)
- Expõe uma função record(event_name, **attrs) para registrar eventos
  dentro do span (ex.: guardrail acionado, chunk usado, etapa concluída)
- Ao final, registra a duração total da interação como atributo do span

Ver docs/CRITERIOS-DE-ACEITE.md para o que a demo final espera visualizar
no trace.
"""

from contextlib import contextmanager


@contextmanager
def trace_interaction(conversation_id: str):
    raise NotImplementedError
