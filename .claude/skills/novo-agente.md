# Skill: novo-agente

Cria um novo agente seguindo o padrão `agent_platform_oci` adaptado para esta PoC.

## Contexto desta PoC

Esta PoC é um subconjunto simplificado do `agent_platform_oci`. A diferença
principal é que aqui **não usamos LangGraph nem AgentRuntimeMixin completo** —
o orquestrador é um wrapper FastAPI simples em `gateway/app.py`. Mesmo assim,
a estrutura de cada agente segue os mesmos contratos do framework real:

- O agente recebe um `QueryResult` do RAG e o contexto da sessão
- Usa `build_messages()` para montar o payload LLM (sem inventar quando `found=False`)
- Emite eventos de tracing via `agent/tracer.py` (equivalente local ao IC/NOC/GRL)
- Retorna um texto de resposta para o orquestrador

## Passos

### 1. Responder as perguntas de design antes de escrever código

```
Qual problema de negócio este agente resolve?
Que dados ele precisa para responder com segurança?
Que ferramentas/fontes fornecem esses dados? (RAG? tool call? ambos?)
Quais regras de domínio bloqueiam ou autorizam uma ação?
Que resposta deve chegar ao usuário?
Quais eventos de trace são necessários para auditoria?
```

### 2. Criar o arquivo do agente

Caminho: `agent/<nome_dominio>_agent.py`

Template mínimo:

```python
"""Agente de <domínio> — ver docs/ARQUITETURA.md e docs/PROPOSTA-POC.md."""

from rag_pipeline.models import QueryResult
from agent.models import GuardrailResult
from agent import prompt as agent_prompt
from agent import llm_client


class <NomeDominio>Agent:
    """Responde perguntas sobre <domínio> com base em evidência RAG."""

    name = "<nome_dominio>_agent"

    def run(self, question: str, query_result: QueryResult) -> str:
        """Executa o agente: monta prompt, chama LLM, retorna resposta.

        Contrato de segurança: se query_result.found for False, retorna
        not_found_response() sem chamar o LLM — nunca inventar.
        """
        built_prompt = agent_prompt.build_prompt(question, query_result)
        if built_prompt is None:
            return agent_prompt.not_found_response()

        return llm_client.complete(built_prompt)
```

### 3. Registrar na config

Adicionar em `config/agents.yaml` (criar se não existir):

```yaml
agents:
  <nome_dominio>_agent:
    description: "<descrição curta>"
    route: "<nome_dominio>"
    rag_namespace: "<nome_dominio>"  # namespace no vector store
```

### 4. Adicionar ao roteador/grafo

No arquivo de orquestração (ex.: `gateway/app.py` ou `workflows/agent_graph.py`
quando o grafo LangGraph for implementado), registrar o novo agente como nó.

### 5. Escrever testes

Caminho: `tests/test_<nome_dominio>_agent.py`

O teste mínimo deve cobrir:
- resposta correta quando `query_result.found = True` com chunk sintético
- retorno de `not_found_response()` quando `query_result.found = False` (sem
  chamar o LLM — usar mock/spy para confirmar)
- integração com guardrails: verificar que resposta com PII é mascarada pelo
  guardrail de output antes de sair do agente

### 6. Atualizar o CLAUDE.md (se existir) ou STATE.md

Registrar o novo agente na seção de componentes implementados para que futuras
sessões tenham contexto.

## Regras que nunca mudam (herdadas do framework real)

| Regra | Fonte |
|---|---|
| Sem evidência RAG (`found=False`) → não chamar LLM, retornar resposta padrão | `agent/prompt.py` contrato, SPEC-002 do `agent_platform_oci` |
| Dados sensíveis (PII) nunca chegam crus ao LLM | `agent/guardrails/input_guardrail.py`, SPEC-005 |
| Prompt do sistema contém regras permanentes; evidência vai no papel `user` | Padrão de mensagens do `agent_platform_oci` — ver README do framework |
| Agente retorna fonte (`source_document_id`) junto com a resposta | Auditabilidade — usado pelo `judge.py` para detectar possível alucinação |
| Eventos de trace são fail-open: ausência de tracer não quebra o fluxo | Mesmo comportamento do `_emit_ic()` do `AgentRuntimeMixin` real |

## Antipadrões a evitar

- Mandar o estado completo da sessão pro LLM — selecionar só os campos necessários
- Mandar o objeto `QueryResult` bruto — resumir para `found`, `text`, `source`
- Colocar regras permanentes de domínio só no papel `user` — pertencem ao `system`
- Duplicar histórico que o framework já gerencia via memória/summary
- Agente inventar quando a ferramenta falhou — explicitar ausência de evidência
