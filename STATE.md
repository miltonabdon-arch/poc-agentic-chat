# State

**Last Updated:** 2026-08-06
**Escopo deste arquivo:** este `STATE.md` é local a este repositório (PoC de 2
semanas do "Agente de Catálogo"). Ele **não substitui** o `STATE.md` do
projeto principal do Agente de Planos e Ofertas (POV) — é um resumo extraído
apenas do contexto que esta PoC referencia em `docs/PROPOSTA-POC.md`,
`docs/ARQUITETURA.md` e `agent/judge.py`. Decisões de escopo de negócio,
propostas comerciais e demais blockers do projeto principal vivem no
`STATE.md` do repositório principal, não aqui.

**Current Work:** Repositório criado em 2026-08-04 como esqueleto para o
time implementar (contratos de dados, testes e documentação completos,
módulos com `NotImplementedError`). Auditoria de 2026-08-05 corrigiu
vazamentos de solução (thresholds/fórmulas calibradas expostos nos docs),
migrou CI para GitHub Actions e fechou gaps de teste/lint (ver commit
`be2ea6b`). Apresentação de kickoff (`docs/apresentacao-poc.html`) adicionada
em 2026-08-06 para alinhar o time no Dia 1. Judge panel multi-modelo
(Claude + DeepSeek + Gemini) em 2026-08-07 emitiu NO-GO: o esqueleto não
integrava de fato o `agent_platform_oci`, apenas bibliotecas genéricas
usadas por ele — ver AD-008 abaixo para a correção aplicada.

---

## Recent Decisions

### AD-007: Adotar `agent_platform_oci` como base técnica obrigatória e confirmada de construção (2026-07-31)

**Decision:** O framework
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci)
deixa de ser tratado como stack "pendente de confirmação" e passa a ser a
premissa assumida e obrigatória para todos os agentes e entregáveis já
especificados do Agente POV — incluindo esta PoC, que existe justamente para
validar essa premissa na prática (rodar o framework de ponta a ponta, não
apenas ler a documentação).
**Reason:** Instrução explícita do usuário no projeto principal (2026-07-31).
Uma análise documental do repositório público
(`relatorio-aderencia-agent-platform-oci.md`, no repositório principal) já
havia confirmado que o framework é real e maduro (20 SPECs internas),
compatível com a arquitetura desenhada — mas essa análise foi feita apenas
lendo documentação remota, sem clonar o código nem rodar nada. Esta PoC é o
próximo passo natural dessa decisão.
**Impact para esta PoC:** todo o desenho em `docs/ARQUITETURA.md` (Router
LangGraph, Guardrails, `AgentRuntimeMixin`, Channel Gateway, Observability
Tracer, Vector Store) é mapeado deliberadamente 1:1 contra as SPECs do
framework real — ver tabela "Mapeamento para as SPECs do `agent_platform_oci`"
em `docs/ARQUITETURA.md`.

---

### AD-008: Integrar de fato o pacote `agent_framework` real do `agent_platform_oci` (2026-08-07)

**Decision:** O esqueleto passa a depender do pacote `agent_framework`
instalado via `pip install git+https://github.com/hoshikawa2/agent_platform_oci.git@main#subdirectory=libs/agent_framework`
(ver `requirements.txt`), em vez de apenas usar bibliotecas genéricas
(LangGraph, FastAPI, Chroma) que o framework também usa. Componentes
integrados de fato: `agent_framework.llm.providers.create_llm()` (LLM),
`agent_framework.guardrails.PiiMaskRail` (mascaramento de PII),
`agent_framework.channels.base.ChannelMessage`/`ChannelResponse` (contrato
de canal), `agent_framework.observability.otel.OpenTelemetryProvider`
(tracing). Vector store **não** foi integrado (ver exceção documentada
abaixo).
**Reason:** Um judge panel multi-modelo (Claude Sonnet, DeepSeek-V4-Pro,
Gemini 3.1 Pro, com síntese/consenso via Haiku) rodado em 2026-08-07 para
validar se esta PoC estava pronta para o time começar emitiu **NO-GO**: 2
dos 3 revisores confirmaram, lendo o código real do esqueleto, que nenhum
módulo importava/estendia o `agent_platform_oci` — o `requirements.txt` não
declarava a dependência, o `Dockerfile` não clonava o repositório, e
`AgentRuntimeMixin` era reimplementado do zero como "wrapper mínimo
equivalente" em vez de importado. Consequência: os critérios de aceite
poderiam passar 100% sem que uma linha do framework real fosse executada,
invalidando a conclusão que a PROPOSTA-POC.md promete (que o risco "o
framework funciona?" fica resolvido ao fim das 2 semanas).
**Impact:** `docs/ARQUITETURA.md` (tabela "Mapeamento para as SPECs") e
`docs/PROPOSTA-POC.md` (seção 6) foram atualizados para registrar
explicitamente, componente a componente, o que agora é integração real e o
que continua sendo implementação própria desta PoC (com racional para cada
exceção) — não há mais alegação implícita de "equivalente" onde na verdade
não há dependência real.
**Exceção documentada — vector store:** `agent_framework.rag.vector_store.SQLiteVectorStore`
não foi adotado porque seu `add_texts()` sempre gera um novo id (`uuid4`),
sem upsert por chave externa estável — incompatível com o requisito de
reingestão idempotente por `chunk_id` que `tests/test_ingestao.py` já
exigia antes desta mudança. Chroma local foi mantido, pois suporta upsert
nativo por id. Esta é uma lacuna de API do framework real descoberta durante
esta correção, não coberta pela análise documental original (ver
`docs/referencias/relatorio-aderencia-agent-platform-oci-resumo.md`).
**Achado adicional (ALTO, ainda aberto):** o `agent_platform_oci` também
publica um template pronto (`templates/agent_template_backend_day_zero`)
desenhado para começar um agente do zero sobre o framework, com `.env` já
configurado 100% local (`LLM_PROVIDER=mock`, `VECTOR_STORE_PROVIDER=sqlite`,
`EMBEDDING_PROVIDER=mock`, `SESSION_REPOSITORY_PROVIDER=sqlite`). Esta PoC
não foi remodelada em cima desse template (o esqueleto já existia com
estrutura própria de pastas por papel — `rag_pipeline/`, `agent/`,
`gateway/`, `orchestrator/` — alinhada a `PAPEIS-E-ENTREGAVEIS.md`); ficou
como aprendizado a avaliar no relatório final de achados (seção 10 de
`PROPOSTA-POC.md`) se a estrutura de pastas por papel desta PoC deveria, em
uma próxima iteração, se aproximar mais da estrutura de pastas do template
oficial (`app/agents/`, `app/workflows/`, `config/*.yaml`).

---

## Active Blockers (relevantes para esta PoC)

### B-006 (herdado, rebaixado): Divergência entre instância OCI real e repositório público analisado

**Status:** não bloqueia esta PoC — é o risco remanescente que a PoC existe
para reduzir na parte que está sob seu controle (a base pública), não na
parte que não está (customizações internas não divulgadas da TIM/Oracle).
**Impact:** se a instância real do `agent_platform_oci` que a TIM provisionar
divergir do repositório público analisado (fork/customização interna), parte
do aprendizado desta PoC sobre contratos de dados e mapeamento de SPECs pode
precisar de ajuste no projeto real.
**Mitigação nesta PoC:** os 3 contratos de dados (`QueryResult`,
`GuardrailResult`, `Interaction`) seguem deliberadamente o mesmo vocabulário
dos designs já produzidos no projeto principal — qualquer aprendizado desta
PoC sobre esses contratos é diretamente reaproveitável, reduzindo (não
eliminando) esse risco.
**Resolution:** fora do controle desta PoC — depende de confirmação da
TIM/Oracle sobre a instância real, acompanhada no `STATE.md` do projeto
principal.

---

## Deferred Ideas (relevantes para esta PoC)

- [ ] Judge leve offline com Golden Standard Dataset completo — esta PoC
  implementa apenas uma checagem simples por amostragem (ver
  `agent/judge.py`, `docs/ARQUITETURA.md`); o Golden Standard Dataset
  completo é Deferred Idea do projeto principal, fora do escopo das 2
  semanas desta PoC.
- [ ] State Store real compartilhado entre agentes (Redis/AlloyDB) — próxima
  extensão natural sugerida no `README.md` desta PoC, não implementada.

---

## Todos (desta PoC)

- [x] AD-008: integrar de fato o pacote `agent_framework` real (LLM,
  guardrail de PII, contrato de canal, tracer) — 2026-08-07
- [x] Verificar que `pip install` do `agent-framework` via git+subdirectory
  funciona sem erro (achado ALTO do judge panel) — validado em 2026-08-07
  com Python 3.11 (o framework exige `>=3.10`; Python 3.9 falha ao resolver
  `mcp>=1.9.0`, então confirmar Python 3.10+ no Dia 1). Instalação completa
  (`agent-framework-0.1.0` + ~120 dependências transitivas, incluindo
  `oci`, `langgraph`, `oracledb`) concluída com sucesso; `PiiMaskRail` e
  `create_llm(LLM_PROVIDER=mock)` testados e funcionando de ponta a ponta
  contra o pacote real instalado (não apenas lendo o código-fonte remoto)
- [ ] Concluir as 4 fatias de implementação (Data Engineer, AI Scientist,
  Backend/Integração, AI Developer Sr) — ver `docs/PAPEIS-E-ENTREGAVEIS.md`
- [ ] Checkpoint 1 (Dia 5): ingestão + RAG funcionando ponta a ponta
- [ ] Checkpoint 2 (Dia 9): primeira demo end-to-end via `docker-compose up`
- [ ] Demo final + relatório de achados técnicos (1-2 páginas) sobre o
  `agent_platform_oci` — ver `docs/PROPOSTA-POC.md`, seção 10
