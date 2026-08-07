"""Observability Tracer - usa OpenTelemetryProvider real do agent_framework
(agent_framework.observability.otel), equivalente simplificado de SPEC-007
(o framework real tambem integra Langfuse + eventos IC/NOC/GRL gerenciados,
fora do escopo minimo desta PoC - ver docs/ARQUITETURA.md).

trace_interaction() e um context manager que abre um span por interação
(conversation_id como atributo) e expõe record(event_name, **attrs) para
registrar eventos dentro do span (guardrail acionado, chunk usado, etapa
concluída). Se ENABLE_OTEL=false (default), o provider real do framework
já faz no-op sem lançar erro - o span é None e record() apenas ignora.

Ver docs/CRITERIOS-DE-ACEITE.md para o que a demo final espera visualizar
no trace.
"""

import time
from contextlib import contextmanager

from agent_framework.config.settings import settings
from agent_framework.observability.otel import OpenTelemetryProvider

_provider = OpenTelemetryProvider(settings)


@contextmanager
def trace_interaction(conversation_id: str):
    started_at = time.monotonic()
    with _provider.span("agent.interact", {"conversation_id": conversation_id}) as span:

        def record(event_name: str, **attrs) -> None:
            if span is None:
                return
            for key, value in attrs.items():
                span.set_attribute(f"{event_name}.{key}", value if isinstance(value, (str, int, float, bool)) else str(value))

        yield record

        if span is not None:
            span.set_attribute("duration_ms", int((time.monotonic() - started_at) * 1000))
