"""Cliente de LLM - usa o factory create_llm real do agent_framework.

LLM_PROVIDER (ver .env.example) decide o provider concreto: "mock" (sem
credencial de nuvem, usado por padrão nesta PoC) ou "oci_openai" (com
credencial de OCI Generative AI de desenvolvimento, se disponível - ver
docs/PROPOSTA-POC.md, secao 6). A escolha do provider de produção continua
sendo decisão do projeto real - aqui o objetivo é validar o fluxo.
"""

import asyncio

from agent_framework.config.settings import settings
from agent_framework.llm.providers import create_llm

_llm = create_llm(settings)


def complete(prompt: str) -> str:
    return asyncio.run(_llm.ainvoke([{"role": "user", "content": prompt}]))
