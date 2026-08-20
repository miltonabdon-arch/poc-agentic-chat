# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este repositório

PoC técnica de 2 semanas do "Agente de Catálogo" da TIM — valida, em ambiente
100% local, a viabilidade arquitetural do framework
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci) como
base do Agente de Planos e Ofertas (POV). **Não é o repositório de
implementação final.** Ver [`docs/PROPOSTA-POC.md`](docs/PROPOSTA-POC.md) e
[`STATE.md`](STATE.md) para o estado corrente de decisões e pendências.

## Comandos principais

```bash
# Setup
cp .env.example .env          # preencher LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
                              # opcional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
pip install -r requirements.txt

# Ingestão (popula Chroma local com data/catalogo/)
python scripts/run_ingestao.py

# Demo ponta a ponta (5 perguntas de docs/CRITERIOS-DE-ACEITE.md)
python scripts/run_demo.py

# Demo interativa com UI Chainlit (3 terminais separados ou via VSCode "Apresentação Completa")
scripts/start_mock.ps1        # terminal 1 — mock services :8001
scripts/start_gateway.ps1     # terminal 2 — gateway :8000
scripts/start_chainlit.ps1    # terminal 3 — UI Chainlit :8080

# Serviços separados por perfil (profile):
docker compose --profile infra up -d   # mock-services + langfuse + langfuse-db
docker compose --profile app up -d    # gateway (requer infra no ar)
docker compose --profile infra --profile app up -d  # tudo junto

# Langfuse dashboard disponível em http://localhost:3000
# Na primeira execução: criar projeto em :3000 e copiar as chaves para .env

# Lint
ruff check .

# Testes unitários (sem LLM, sem ingestão prévia)
pytest -m "not integration"

# Testes por fatia de responsabilidade
pytest -m "not integration" tests/test_ingestao.py    # Data Engineer
pytest -m "not integration" tests/test_agent.py       # AI Scientist
pytest -m "not integration" tests/test_gateway.py     # Backend
pytest -m "not integration" tests/test_integracao.py  # AI Developer Sr (integração)

# Testes de integração (requer ingestão prévia + LLM configurado)
pytest -m integration
```

CI (GitHub Actions) roda em todo push: `ruff check .` → `pytest -m "not integration"` → `docker build`.

## Arquitetura

Cada módulo é de responsabilidade de um papel do time (ver
[`docs/PAPEIS-E-ENTREGAVEIS.md`](docs/PAPEIS-E-ENTREGAVEIS.md)):

```
rag_pipeline/                   ← Data Engineer (Ana): ingestão Markdown → Chroma + API de consulta RAG
agent/                          ← AI Scientist (Gustavo): prompt, guardrails input/output, judge offline
gateway/                        ← Backend/Integração (Kirllen): FastAPI runtime + Channel Gateway + SSE /trace
orchestrator/                   ← AI Developer Sr (Igor): grafo LangGraph + tracer 4 camadas + broadcaster
orchestrator/trace_broadcaster.py ← pub/sub asyncio.Queue entre tracer e consumidores SSE/Chainlit
mock_services/                  ← Backend/Integração (Kirllen): agentes externos mock + CRM fake + middleware de log
chainlit_app.py                 ← UI demo: cliente HTTP do gateway, processa 11 tipos de evento SSE com exibição seletiva (FLOW apenas sub-componentes, GRL apenas quando bloqueado, NOC genérico suprimido) e TaskList de 5 fases
data/catalogo/                  ← dados sintéticos de entrada da ingestão (arquivos .md com front-matter)
```

**Fluxo de uma requisição (API):**
`POST /agent/interact` → `gateway/app.py` → `gateway/channel_gateway.normalize()` →
`orchestrator/graph.run_interaction()` → guardrail de input → roteamento por intenção →
nó de domínio (estratégia variável: RAG+LLM / CRM+LLM / handoff sem LLM) →
guardrail de output → resposta.

**Fluxo de observabilidade em tempo real (UI Chainlit):**
`chainlit_app.py` abre `GET /trace` (SSE) antes de enviar a mensagem → cada nó e sub-componente
do grafo chama `orchestrator/tracer.py` → tracer publica em `trace_broadcaster.py` →
broadcaster entrega o evento na fila SSE do cliente → Chainlit exibe como step expansível
com ícone por tipo de evento (⚙️ FLOW · 🤖 LLM · 🔍 RAG · 🎭 MOCK · 📊 STATE · 🏁 ORCH · ⚖️ JUDGE · 🗺️ GRAPH · 🛡️ GRL · ✅ NOC).

`orchestrator/graph.run_interaction()` roteia por intenção via `EnterpriseRouter` e
encaminha para: o fluxo RAG do catálogo (RAG + LLM), handoff para `mock_services`
(cancellation/deals — sem LLM, resposta vem do agente externo), ou resposta direta
(billing, eligibility, simulation, supervisor — CRM mock + LLM). Guardrails
(input/output) e routing_decision são puramente determinísticos, sem LLM.

## Contratos de dados entre módulos

Três structs são a cola entre as fatias (definidas em `rag_pipeline/models.py` e
`agent/models.py`):

| Struct | Produtor → Consumidor | Campos-chave |
|---|---|---|
| `QueryResult` | `rag_pipeline/query_api.py` → `agent/prompt.py` | `found`, `chunk_id`, `text`, `source_document_id`, `confidence_score` |
| `GuardrailResult` | `agent/guardrails/*.py` → `orchestrator/graph.py` | `guardrail_type`, `violation`, `action_taken` |
| `Interaction` | `gateway/channel_gateway.py` → `orchestrator/graph.py` | `conversation_id`, `channel`, `message`, `timestamp` |

## Estado atual de implementação

Todos os módulos estão implementados (código funcional, sem `NotImplementedError`):

- `gateway/app.py`, `gateway/channel_gateway.py` — `POST /agent/interact`, `GET /trace` (SSE), redirect `/chainlit`
- `orchestrator/graph.py` — grafo LangGraph completo com 11 nós, 3 arestas condicionais, helpers de negócio com FLOW/MOCK/RAG/LLM/JUDGE/GRAPH/ORCH/STATE events; retry automático (1× após 2s) em `APITimeoutError` em `_call_llm_and_trace()`
- `orchestrator/trace_broadcaster.py` — pub/sub asyncio.Queue para SSE e Chainlit
- `orchestrator/tracer.py` — 4 camadas: AgentObserver+Langfuse, log local estruturado, broadcaster SSE; `trace_flow()` e `NODE_OWNERS`
- `chainlit_app.py` — processa 11 tipos de evento SSE com exibição seletiva: FLOW apenas para sub-componentes (rag.query, llm.complete, mock.*), GRL apenas quando há bloqueio/violação, NOC genérico suprimido (`_STEP_NODES = set()`), STATE suprimido para routing_decision e output_guardrails; TaskList de 5 fases; corrige steps orphans
- `mock_services/` — agentes mock (cancellation, deals, plans) + CRM fake + middleware de log estruturado `[MOCK] REQUEST/RESPONSE`
- `agent/judge.py` — `judge_batch()` implementado
- `agent/prompt.py` — `build_prompt()`, `not_found_response()`, `build_crm_prompt()`, `build_supervisor_prompt()`, `build_not_found_prompt()` implementados
- `agent/guardrails/input_guardrail.py` — `check_input()` implementado
- `agent/guardrails/output_guardrail.py` — `check_output()` implementado
- `agent/llm_client.py` — `complete()` com `timeout=30s` e re-raise tipado (`RuntimeError: llm_complete_failed:...`)
- `rag_pipeline/vectorizer.py` — Chroma com modelo multilíngue (`paraphrase-multilingual-MiniLM-L12-v2`) e métrica cosine
- `rag_pipeline/query_api.py` — busca por similaridade com re-ranking via `CrossEncoder` (BAAI/bge-reranker-v2-m3)

## Tipos de evento de observabilidade

O tracer emite dois grupos de eventos:

**Do framework `agent_platform_oci` (via `AgentObserver`):**
- `IC` — Interaction Created: início da sessão; ancora o `session_id`
- `NOC` — Node Completed: nó do grafo LangGraph concluído
- `GRL` — GuaRaiL: guardrail de input ou output acionado (registra violação + blocked)

**Extensões locais da PoC (via `trace_flow()` e `trace_interaction()`):**
- `FLOW` — par ENTER/EXIT em torno de cada componente; abre step no Chainlit imediatamente (real-time)
- `LLM` — chamada ao modelo; registra modelo, tamanho do prompt/resposta e latência
- `RAG` — busca no Chroma; registra `found`, `chunk_id`, score e latência
- `MOCK` — chamada HTTP a `mock_services`; registra serviço, endpoint, HTTP status e latência
- `JUDGE` — avaliação offline de qualidade via `judge_batch()`
- `GRAPH` — topologia compilada; emitido no início de `run_interaction()` (estado inicial omitido — sempre vazio no arranque)
- `ORCH` — resultado executivo do pipeline (rota, intenção, latência, estado final); emitido ao fim de `run_interaction()`
- `STATE` — δ do `GraphState` após cada nó; produzido pelo loop `astream` sem alterar nenhum nó

## Decisões técnicas relevantes

- **Vector store:** Chroma local embutido (`PersistentClient`, `./chroma_data/`), sem servidor separado. Representa o ADW do projeto real.
- **Embedding:** `paraphrase-multilingual-MiniLM-L12-v2` (multilíngue), métrica cosine — escolha explícita para nomes de planos em português.
- **Re-ranking:** `BAAI/bge-reranker-v2-m3` (CrossEncoder) em `rag_pipeline/query_api.py` para refinar o top-5 antes de aplicar threshold; threshold calibrado empiricamente em `0.60` (placeholder inicial: `0.70`).
- **Orquestração:** LangGraph — mesma lib do `agent_platform_oci` real. `build_graph()` implementado com 11 nós e roteamento via `EnterpriseRouter`.
- **Framework `agent_platform_oci`:** integração real foi tentada (AD-008) e revertida (AD-009); vendorizado localmente (AD-010). Código usa FastAPI, LangGraph, OpenAI client e vendor local.
- **Mock services:** `mock_services/` roda como serviço separado (`:8001`) e simula CRM, cancelamento, deals e simulação de planos. Middleware de log estruturado emite `[MOCK] REQUEST/RESPONSE` com latência e `x-conversation-id` em cada request.
- **UI de demo:** Chainlit standalone em `:8080`. `chainlit_app.py` não importa nenhum módulo interno — comunica-se exclusivamente via HTTP com o gateway. Ícones por tipo de evento (⚙️ FLOW · 🤖 LLM · 🔍 RAG · 🎭 MOCK · 📊 STATE · 🏁 ORCH · ⚖️ JUDGE · 🗺️ GRAPH) e TaskList com 5 fases tornam o pipeline visível em tempo real, com exibição seletiva (GRL/NOC/FLOW de nós suprimidos quando sem conteúdo informativo).
- **Observabilidade — 4 camadas:** `orchestrator/tracer.py` publica cada evento em (1) `AgentObserver` com `LangfuseAnalyticsPublisher` injetado para IC/NOC/GRL (produção: publisher OCI; local: Langfuse), (2) log local estruturado `TRACE|tipo|chave=valor` para grep no terminal, (3) `trace_broadcaster.py` (asyncio.Queue) para clientes SSE em tempo real, e (4) Langfuse auto-hospedado via docker-compose (dashboard em `:3000`) quando `LANGFUSE_PUBLIC_KEY` está configurado.
- **LLM client:** `agent/llm_client.py` usa `timeout=30s` no cliente OpenAI; falhas de rede/API são re-raised como `RuntimeError("llm_complete_failed: ...")` para grep preciso no log. `_call_llm_and_trace()` em `orchestrator/graph.py` faz retry automático (1× após 2s) em `APITimeoutError`; outros erros propagam imediatamente.
- **Variáveis de ambiente:** além de `LLM_BASE_URL/API_KEY/MODEL`, o sistema usa `MOCK_SERVICES_URL` (graph.py), `GATEWAY_URL` (chainlit_app.py), `CHAINLIT_URL` (gateway/app.py) e `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` (tracer.py). Todas documentadas em `.env.example`.
