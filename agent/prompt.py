"""Prompt do agente - monta o contexto para o LLM.

Filosofia central: sem evidência (found=False), nunca inventar — responder
explicitamente que a informação não foi encontrada. Mesma filosofia de
'sem evidência, sem invenção' de pipeline-rag-base/design.md.

Arquitetura de seções (ordem de montagem em build_prompt):

  [SISTEMA]     identidade, tom e regras fixas — enviado como role:system
                via llm_client.complete(system=build_system_prompt())
  [FERRAMENTAS] MCPs e APIs disponíveis (omitido quando vazio)
  [CONTEXTO]    evidências RAG + resultados de API já resolvidos pelo orquestrador
  [HISTÓRICO]   turnos anteriores da conversa (omitido quando vazio)
  [PERGUNTA]    pergunta do cliente no turno atual

Contratos:
- build_prompt() retorna None se query_result.found for False (o
  orquestrador deve usar not_found_response() nesse caso, sem chamar o LLM)
- build_prompt() é backward-compatible: aceita apenas (question, query_result)
  e os demais parâmetros (tools, api_results, history) são opcionais
- build_system_prompt() retorna a parte estática — separar system/user
  é a base para tool-calling real via MCP
"""

from dataclasses import dataclass, field

from rag_pipeline.models import QueryResult

# ---------------------------------------------------------------------------
# Contratos de contexto externo (MCP / APIs)
# ---------------------------------------------------------------------------


@dataclass
class MCPTool:
    """Descreve um MCP ou API disponível para o agente invocar."""

    name: str
    description: str
    parameters: dict = field(default_factory=dict)


@dataclass
class APIResult:
    """Resultado de uma chamada de API externa já resolvida pelo orquestrador."""

    tool_name: str
    data: dict
    raw_text: str = ""


@dataclass
class ConversationTurn:
    """Um turno da conversa (user ou assistant)."""

    role: str  # "user" | "assistant"
    content: str


# ---------------------------------------------------------------------------
# System prompt (parte estática — role:system)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Você é o Assistente Virtual da TIM, especializado em planos e ofertas de telefonia.

Regras de comportamento:
- Responda APENAS com base nas evidências fornecidas em [CONTEXTO]. Nunca invente informações.
- Jamais fabricar nomes de clientes, CPFs, valores monetários ou datas que não estejam
  explicitamente no [CONTEXTO]. Se não estiver lá, não cite.
- Escreva em prosa fluida, como se estivesse falando — sem listas, sem marcadores,
  sem markdown, sem colchetes ou símbolos especiais.
- Refira-se ao plano pelo nome natural presente na evidência, nunca pelo ID técnico.
- Se a informação não estiver disponível em [CONTEXTO], diga claramente que não encontrou.
- Seja objetivo, cordial e direto.
- Limite sua resposta a no máximo 3 frases. Prefira respostas concisas.\
"""


def build_system_prompt() -> str:
    """Retorna a parte estática do prompt (identidade + regras fixas).

    Deve ser enviado como role:system via llm_client.complete(system=...).
    Separar do contexto RAG é o pré-requisito para tool-calling real (MCPs).
    """
    return _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Mensagem de não encontrado
# ---------------------------------------------------------------------------

_NOT_FOUND_MSG = (
    "Não encontrei essa informação no catálogo de planos e ofertas disponível. "
    "Posso ajudar com dúvidas sobre planos, pacotes de dados, benefícios ou cobertura da TIM."
)


def not_found_response() -> str:
    return _NOT_FOUND_MSG


def build_not_found_prompt(question: str) -> str:
    """Monta prompt para quando o RAG não encontrou resultado acima do threshold."""
    return (
        "[CONTEXTO]\n"
        "Não foi encontrado nenhum plano ou oferta específica correspondente "
        "à pergunta do cliente no catálogo disponível. Não invente dados.\n\n"
        "[INSTRUÇÕES]\n"
        "Informe cordialmente que não localizou esse plano específico. "
        "Sugira que o cliente especifique melhor a necessidade ou pergunte "
        "sobre as categorias disponíveis: pré-pago, controle ou turbo.\n\n"
        f"[PERGUNTA DO CLIENTE]\n{question}"
    )


def build_supervisor_prompt(question: str) -> str:
    """Monta prompt para o nó supervisor — saudações e intenções não mapeadas."""
    return (
        "[PAPEL]\n"
        "Você é o Assistente Virtual da TIM. O cliente iniciou uma conversa "
        "sem especificar um domínio claro, ou fez uma saudação.\n\n"
        "[DOMÍNIOS QUE VOCÊ ATENDE]\n"
        "- Planos e catálogo (dados, ligações, benefícios)\n"
        "- Fatura e cobrança\n"
        "- Cancelamento de serviço\n"
        "- Negociação de débito\n"
        "- Simulação de troca de plano\n"
        "- Elegibilidade para upgrade\n\n"
        f"[MENSAGEM DO CLIENTE]\n{question}"
    )


def build_crm_prompt(question: str, intent: str, api_data: dict) -> str:
    """Monta prompt (role:user) para intents baseados em dados CRM."""
    import json
    context = json.dumps(api_data, ensure_ascii=False, indent=2)
    return (
        f"[CONTEXTO CRM — {intent}]\n{context}\n\n"
        f"[PERGUNTA DO CLIENTE]\n{question}"
    )


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------


def build_prompt(
    question: str,
    query_result: QueryResult,
    *,
    tools: list[MCPTool] | None = None,
    api_results: list[APIResult] | None = None,
    history: list[ConversationTurn] | None = None,
) -> str | None:
    """Monta o prompt completo (role:user) para o LLM.

    Retorna None quando não há evidência RAG (query_result.found=False) —
    o orquestrador deve usar not_found_response() sem chamar o LLM.

    Args:
        question: Pergunta do cliente no turno atual.
        query_result: Resultado da consulta RAG.
        tools: MCPs ou APIs que o agente pode invocar (opcional).
        api_results: Respostas de APIs já resolvidas pelo orquestrador (opcional).
        history: Histórico de turnos anteriores (opcional).
    """
    if not query_result.found:
        return None

    sections: list[str] = []

    if tools:
        tool_lines = ["[FERRAMENTAS DISPONÍVEIS]"]
        for t in tools:
            tool_lines.append(f"- {t.name}: {t.description}")
        sections.append("\n".join(tool_lines))

    confidence = query_result.confidence_score
    confidence_note = (
        " (confiança baixa — seja mais cauteloso ao afirmar detalhes)"
        if confidence < 0.5
        else ""
    )
    context_lines = [
        "[CONTEXTO]",
        f"[fonte interno: {query_result.source_document_id}{confidence_note}]",
        f"Evidência: {query_result.text}",
    ]
    if api_results:
        for api in api_results:
            payload = api.raw_text if api.raw_text else str(api.data)
            context_lines.append(f"[{api.tool_name}]: {payload}")
    sections.append("\n".join(context_lines))

    if history:
        hist_lines = ["[HISTÓRICO]"]
        for turn in history:
            label = "Cliente" if turn.role == "user" else "Assistente"
            hist_lines.append(f"{label}: {turn.content}")
        sections.append("\n".join(hist_lines))

    sections.append(f"[PERGUNTA DO CLIENTE]\n{question}")

    return "\n\n".join(sections)
