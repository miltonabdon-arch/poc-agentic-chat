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
| [`STATE.md`](STATE.md) | Decisões, blockers e todos específicos desta PoC (resumo local — não substitui o `STATE.md` do projeto principal) |

## Estrutura do repositório

```
poc-agentic-chat/
├── docs/                     # documentação (ver índice acima)
│   └── diagrams/              # fontes .mmd dos diagramas de arquitetura
├── data/catalogo/             # dados sintéticos do catálogo (entrada da ingestão)
├── rag_pipeline/               # Data Engineer — ingestão e consulta RAG
├── agent/                      # AI Scientist / LLM Specialist — prompt, guardrails, judge
├── gateway/                     # Backend / Integração — Channel Gateway + runtime FastAPI
├── orchestrator/                # AI Developer Sr — grafo/router + observabilidade
├── tests/                       # testes por camada
├── scripts/                     # scripts de setup e demo local
├── docker-compose.yml            # sobe vector store local + app, sem dependência de nuvem
├── .github/workflows/ci.yml       # pipeline CI: lint + testes + build
├── requirements.txt
└── .env.example
```

## Requisitos

- **Python 3.10+** (mesma faixa de versão do `agent_platform_oci` real,
  confirmada em 3.12/3.13 no `relatorio-aderencia-agent-platform-oci.md`) —
  o código usa sintaxe de union types moderna (`str | None`), incompatível
  com Python 3.9. Se seu Python padrão for mais antigo, use `pyenv`/`venv`
  com uma versão 3.10+ antes de instalar as dependências.
- Docker + Docker Compose (para subir o serviço via `docker-compose.yml`)

## Quick start local

```bash
cp .env.example .env
pip install -r requirements.txt
python scripts/run_ingestao.py         # popula o vector store local (Chroma embutido) com data/catalogo/
python scripts/run_demo.py             # roda o agente localmente com as perguntas de exemplo
docker compose up -d                    # opcional: sobe o serviço FastAPI completo (gateway/app.py)
```

Detalhes de cada etapa em `docs/INGESTAO.md` e `docs/ARQUITETURA.md`.

## Estado do repositório

Este repositório contém os **contratos de dados, testes e documentação
completos**, mas os módulos de implementação estão deliberadamente vazios
(`raise NotImplementedError`) — é o ponto de partida da PoC, não o
resultado. Cada papel implementa sua fatia (ver
`docs/PAPEIS-E-ENTREGAVEIS.md`) até os testes correspondentes passarem:

```bash
pytest -m "not integration" tests/test_ingestao.py    # Data Engineer
pytest -m "not integration" tests/test_agent.py       # AI Scientist / LLM Specialist
pytest -m "not integration" tests/test_gateway.py     # Backend / Integração
pytest -m "not integration" tests/test_integracao.py  # AI Developer Sr (após as 3 fatias acima)
```

Os comentários `TODO` em cada módulo apontam o contrato esperado e o teste
correspondente — não é necessário adivinhar o formato de retorno.
