# PoC — Agente de Catálogo sobre `agent_platform_oci`

PoC técnica de 2 semanas para validar, em ambiente local (sem custo de nuvem), a
viabilidade arquitetural do framework
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci) como
base de construção do Agente de Planos e Ofertas (POV) da TIM.

> Este repositório é **novo e dedicado à PoC** — não faz parte do repositório
> de implementação final do Agente POV. Ver `docs/PROPOSTA-POC.md` para o
> objetivo completo e critérios de sucesso.

## Índice de documentação

| Documento | Conteúdo |
|---|---|
| [`docs/apresentacao-poc.html`](docs/apresentacao-poc.html) | **Apresentação de kickoff** (slides navegáveis) — abrir no navegador para o time |
| [`docs/PROPOSTA-POC.md`](docs/PROPOSTA-POC.md) | Objetivo, hipótese, escopo, cronograma de 2 semanas, critérios de sucesso |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | Desenho de arquitetura, mapeamento para as SPECs do `agent_platform_oci`, diagramas |
| [`docs/INGESTAO.md`](docs/INGESTAO.md) | Documentação do pipeline de ingestão RAG — formato de dado, chunking, vetorização, como rodar |
| [`docs/PAPEIS-E-ENTREGAVEIS.md`](docs/PAPEIS-E-ENTREGAVEIS.md) | O que cada papel do time entrega, dia a dia das 2 semanas |
| [`docs/CRITERIOS-DE-ACEITE.md`](docs/CRITERIOS-DE-ACEITE.md) | Checklist de demonstração final |
| [`STATE.md`](STATE.md) | Decisões, estado atual e histórico de ADs desta PoC |
| [`docs/referencias/`](docs/referencias/) | Resumos de documentos do projeto principal citados pelos docs acima |

## Estrutura do repositório

```
poc-agentic-chat/
├── docs/                     # documentação (ver índice acima)
│   └── diagrams/              # fontes .mmd dos diagramas de arquitetura
├── data/catalogo/             # dados sintéticos do catálogo (entrada da ingestão)
├── rag_pipeline/               # Data Engineer (Ana) — ingestão e consulta RAG
├── agent/                      # AI Scientist (Gustavo) — prompt, guardrails, judge
├── gateway/                     # Backend/Integração (Kirllen) — Channel Gateway + runtime FastAPI
├── orchestrator/                # AI Developer Sr (Igor) — grafo LangGraph + tracer 4 camadas
├── mock_services/               # Backend/Integração (Kirllen) — agentes mock + CRM fake
├── tests/                       # testes por camada
├── scripts/                     # scripts de setup e demo local
├── docker-compose.yml            # app + mock-services + langfuse + langfuse-db
├── .github/workflows/ci.yml       # pipeline CI: lint + testes + build
├── requirements.txt
└── .env.example
```

## Requisitos

- **Python 3.10+** (mesma faixa de versão do `agent_platform_oci` real,
  confirmada em 3.12/3.13) — o código usa sintaxe de union types moderna
  (`str | None`), incompatível com Python 3.9.
- **Docker + Docker Compose** — para subir os serviços via profiles:
  `--profile infra` (mock + Langfuse + DB) e `--profile app` (gateway).

## Quick start local

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# Preencher obrigatoriamente: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
# Opcional: LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY (ver passo 4)

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Ingestão — popula o Chroma local com data/catalogo/
python scripts/run_ingestao.py

# 4. Subir os serviços de infraestrutura (mock + Langfuse)
docker compose --profile infra up -d

# Primeira execução do Langfuse: acessar http://localhost:3000,
# criar um projeto e copiar as chaves para LANGFUSE_PUBLIC_KEY/SECRET_KEY no .env
# (sem as chaves, o tracer opera nas camadas 1–3 sem enviar ao Langfuse)

# 5. Subir a aplicação (gateway)
docker compose --profile app up -d

# 5. Rodar a demo automatizada (5 perguntas de docs/CRITERIOS-DE-ACEITE.md)
python scripts/run_demo.py
```

Detalhes de cada etapa em [`docs/INGESTAO.md`](docs/INGESTAO.md) e [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

## Demo interativa com Chainlit

A interface principal de demonstração é a UI Chainlit em `:8080`, que exibe
cada etapa do pipeline em tempo real com steps expansíveis e ícones por tipo de evento:

```bash
make ingest   # uma vez — popula chroma_data/ antes de subir
make up       # sobe infra + gateway + chainlit
```

Ou via VS Code → Run & Debug → **"Apresentação Completa"** → F5 (modo local sem Docker).

Cada componente do pipeline aparece como step expansível imediatamente ao
ser ativado (não só ao terminar), com ícone por tipo de evento:
🗺️ GRAPH · ✅ NOC · 📊 STATE · ⚙️ FLOW · 🔍 RAG · 🤖 LLM · 🎭 MOCK · ⚖️ JUDGE · 🏁 ORCH · 🛡️ GRL

## Estado do repositório

Todos os módulos estão implementados e funcionais. Os testes passam sem LLM:

```bash
pytest -m "not integration"   # 56 testes unitários passando, sem LLM, sem ingestão prévia
```

Para testes de integração ponta a ponta (requerem LLM configurado e ingestão):

```bash
pytest -m integration
```
