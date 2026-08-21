"""Cliente de LLM - interface compativel com OCI Generative AI ou fallback.

Para os fins desta PoC (ver docs/PROPOSTA-POC.md, secao 6), usa qualquer
provider compativel com a API estilo OpenAI Chat Completions, configuravel
via variaveis de ambiente. A escolha do provider de producao continua sendo
decisao do projeto real - aqui o objetivo e validar o fluxo, nao o provider.
"""

import os

from openai import OpenAI


def get_client() -> OpenAI:
    extra_headers: dict[str, str] = {}
    if os.environ.get("FLOW_TENANT"):
        extra_headers["FlowTenant"] = os.environ["FLOW_TENANT"]
    if os.environ.get("FLOW_AGENT"):
        extra_headers["FlowAgent"] = os.environ["FLOW_AGENT"]
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL"),
        api_key=os.environ.get("LLM_API_KEY", "not-needed-for-local-mock"),
        default_headers=extra_headers or None,
        timeout=30.0,   # G9: evita hang indefinido em falhas de rede
        max_retries=0,  # fail-fast: sem retry interno; o grafo trata o erro
    )


def complete(prompt: str, model: str | None = None, system: str | None = None) -> str:
    """Chama o LLM com prompt do usuário e, opcionalmente, system prompt separado.

    Args:
        prompt: Conteúdo do turno atual (role:user) — saída de agent.prompt.build_prompt().
        model: Modelo a usar (fallback para LLM_MODEL env ou gpt-4o-mini).
        system: System prompt estático (role:system) — saída de agent.prompt.build_system_prompt().
                Habilita tool-calling e MCPs reais que exigem separação de papéis.

    Raises:
        RuntimeError: Wrapa qualquer falha de rede / API com tipo explícito para
                      facilitar grep no log (G9).
    """
    client = get_client()
    model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as exc:
        # Re-raise tipado para o caller distinguir timeout de rede de bad-request
        raise RuntimeError(f"llm_complete_failed: {type(exc).__name__}: {exc}") from exc
