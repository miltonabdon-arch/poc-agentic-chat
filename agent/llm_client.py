"""Cliente de LLM - interface compativel com OCI Generative AI ou fallback.

Para os fins desta PoC (ver docs/PROPOSTA-POC.md, secao 6), usa qualquer
provider compativel com a API estilo OpenAI Chat Completions, configuravel
via variaveis de ambiente. A escolha do provider de producao continua sendo
decisao do projeto real - aqui o objetivo e validar o fluxo, nao o provider.
"""

import os

from openai import OpenAI


def get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY", "not-needed-for-local-mock"),
    )


def complete(prompt: str, model: str | None = None) -> str:
    client = get_client()
    model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content
