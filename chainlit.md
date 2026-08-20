# PoC Agente de Catálogo TIM

Interface de demonstração do pipeline de agentes — valida a arquitetura
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci) em ambiente local.

Faça uma pergunta sobre planos, fatura, cancelamento ou ofertas. Cada componente
do pipeline aparece como step expansível **em tempo real**, com o estado do grafo
evoluindo a cada passo.

## Eventos de observabilidade

| Ícone | Tipo | O que representa |
|---|---|---|
| 🗺️ | `GRAPH` | Grafo LangGraph compilado: nós, ponto de entrada e **estado inicial** |
| ⚙️ | `FLOW` | Cada componente: abre ao entrar, fecha com status ao sair |
| ✅ | `NOC` | Nó do grafo concluído (intenção e rota detectadas) |
| 🛡️ | `GRL` | Guardrail acionado: PII, concorrente, formato |
| 🔍 | `RAG` | Busca no catálogo vetorial (Chroma) — chunk e score |
| 🤖 | `LLM` | Chamada ao modelo — prompt completo, resposta e latência |
| 🎭 | `MOCK` | Chamada HTTP a `mock_services` (CRM, cancelamento, negociação) |
| ⚖️ | `JUDGE` | Avaliação offline: groundedness, consistência, tamanho |
| 📊 | `STATE` | **Δ estado do GraphState após cada nó** — campos que mudaram |
| 🏁 | `ORCH` | Pipeline concluído: rota, RAG hit, latência e **estado final** |

> **Pré-requisito:** gateway (`:8000`) e mock services (`:8001`) devem estar rodando.  
> **Opcional:** Langfuse em `:3000` para traces persistentes entre sessões.
