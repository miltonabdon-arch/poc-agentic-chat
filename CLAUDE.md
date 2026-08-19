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
pip install -r requirements.txt

# Ingestão (popula Chroma local com data/catalogo/)
python scripts/run_ingestao.py

# Demo ponta a ponta (5 perguntas de docs/CRITERIOS-DE-ACEITE.md)
python scripts/run_demo.py

# Demo interativa com UI Chainlit (3 terminais separados ou via VSCode "Apresentação Completa")
scripts/start_mock.ps1        # terminal 1 — mock services :8001
scripts/start_gateway.ps1     # terminal 2 — gateway :8000
scripts/start_chainlit.ps1    # terminal 3 — UI Chainlit :8080

# Serviço completo (FastAPI gateway + mock services)
docker compose up -d

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
rag_pipeline/                   ← Data Engineer: ingestão Markdown → Chroma + API de consulta RAG
agent/                          ← AI Scientist: prompt, guardrails input/output, judge offline
gateway/                        ← Backend/Integração: FastAPI runtime + Channel Gateway + SSE /trace
orchestrator/                   ← AI Developer Sr: grafo LangGraph + tracer 3 camadas + broadcaster
orchestrator/trace_broadcaster.py ← pub/sub asyncio.Queue entre tracer e consumidores SSE/Chainlit
mock_services/                  ← Backend/Integração: agentes externos mockados (cancellation, deals, plans) + CRM fake
chainlit_app.py                 ← UI demo: cliente HTTP do gateway, exibe eventos SSE como steps
data/catalogo/                  ← dados sintéticos de entrada da ingestão (arquivos .md com front-matter)
```

**Fluxo de uma requisição (API):**
`POST /agent/interact` → `gateway/app.py` → `gateway/channel_gateway.normalize()` →
`orchestrator/graph.run_interaction()` → guardrail de input → agente (RAG + LLM) →
guardrail de output → resposta.

**Fluxo de observabilidade em tempo real (UI Chainlit):**
`chainlit_app.py` abre `GET /trace` (SSE) antes de enviar a mensagem → cada nó do grafo
chama `orchestrator/tracer.py` → tracer publica em `trace_broadcaster.py` → broadcaster
entrega o evento na fila SSE do cliente → Chainlit exibe como step expansível.

`orchestrator/graph.run_interaction()` detecta a intenção do usuário por palavras-chave e
encaminha para: o fluxo RAG do catálogo, ou handoff para `mock_services` (cancellation/deals),
ou responde diretamente (billing, elegibilidade, simulação de troca) consultando o CRM mock.

## Contratos de dados entre módulos

Três structs são a cola entre as fatias (definidas em `rag_pipeline/models.py` e
`agent/models.py`):

| Struct | Produtor → Consumidor | Campos-chave |
|---|---|---|
| `QueryResult` | `rag_pipeline/query_api.py` → `agent/prompt.py` | `found`, `chunk_id`, `text`, `source_document_id`, `confidence_score` |
| `GuardrailResult` | `agent/guardrails/*.py` → `orchestrator/graph.py` | `guardrail_type`, `violation`, `action_taken` |
| `Interaction` | `gateway/channel_gateway.py` → `orchestrator/graph.py` | `conversation_id`, `channel`, `message`, `timestamp` |

## Estado atual de implementação

Módulos já implementados (código funcional, não `NotImplementedError`):

- `gateway/app.py`, `gateway/channel_gateway.py` — `POST /agent/interact`, `GET /trace` (SSE), redirect `/chainlit`
- `orchestrator/graph.py` (`run_interaction`) — roteamento por intenção + handoff para mock_services + publica SUMARIO no broadcaster
- `orchestrator/trace_broadcaster.py` — pub/sub asyncio.Queue para SSE e Chainlit
- `orchestrator/tracer.py` — 3 camadas: OCI publisher, log local legível, broadcaster SSE
- `chainlit_app.py` — UI demo interativa; consome `/trace` SSE e `POST /agent/interact` via HTTP
- `mock_services/` — agentes externos mock (cancellation, deals, plans) + CRM fake
- `rag_pipeline/vectorizer.py` — Chroma com modelo multilíngue (`paraphrase-multilingual-MiniLM-L12-v2`) e métrica cosine
- `rag_pipeline/query_api.py` — busca por similaridade com re-ranking via `CrossEncoder` (BAAI/bge-reranker-v2-m3)

Módulos ainda com `NotImplementedError` (aguardam merge de `test_new_branch`):

- `agent/judge.py` — `judge_batch()`
- `agent/prompt.py` — `build_prompt()`, `not_found_response()`
- `agent/guardrails/input_guardrail.py` — `check_input()`
- `agent/guardrails/output_guardrail.py` — `check_output()`
- `orchestrator/graph.py` — `build_graph()` (grafo LangGraph real; `run_interaction` usa roteamento próprio)

## Decisões técnicas relevantes

- **Vector store:** Chroma local embutido (`PersistentClient`, `./chroma_data/`), sem servidor separado. Representa o ADW do projeto real.
- **Embedding:** `paraphrase-multilingual-MiniLM-L12-v2` (multilíngue), métrica cosine — escolha explícita para nomes de planos em português.
- **Re-ranking:** `BAAI/bge-reranker-v2-m3` (CrossEncoder) em `rag_pipeline/query_api.py` para refinar o top-5 antes de aplicar threshold.
- **Orquestração:** LangGraph — mesma lib do `agent_platform_oci` real. O grafo LangGraph completo (`build_graph`) ainda não está implementado; `run_interaction` usa roteamento por palavras-chave como interim.
- **Framework `agent_platform_oci`:** integração real foi tentada (AD-008) e revertida (AD-009) para destravar os merges do time. Código atual usa apenas FastAPI, LangGraph, OpenAI client e OpenTelemetry local.
- **Mock services:** `mock_services/` roda como serviço separado (`http://mock-services:8001` no Docker Compose) e simula CRM, agente de cancelamento, agente de deals e simulação de planos.
- **UI de demo:** Chainlit standalone em `:8080`. `chainlit_app.py` não importa nenhum módulo interno — comunica-se exclusivamente via HTTP com o gateway (`POST /agent/interact`, `GET /trace`). Isso garante que a UI não acople a camada de apresentação à lógica do orquestrador.
- **Observabilidade — 3 camadas:** `orchestrator/tracer.py` publica cada evento em (1) OCI publisher (produção), (2) log local estruturado e legível por humanos, e (3) `trace_broadcaster.py` (asyncio.Queue) para clientes SSE em tempo real. O broadcaster usa padrão pub/sub: cada `GET /trace` recebe sua própria fila independente.

## Pendências críticas (STATE.md)

- Branch `test_new_branch` (gbezerra) com implementação de `agent/` ainda **sem PR aberto** — é a próxima pendência de merge.
- Checkpoint 1 (Dia 5 — ingestão + RAG ponta a ponta) **atrasado** desde 2026-08-10.
- `orchestrator/graph.build_graph()` (grafo LangGraph real) ainda não implementado.
