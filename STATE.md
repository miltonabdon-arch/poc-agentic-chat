# State

**Last Updated:** 2026-08-11
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
em 2026-08-06 para alinhar o time no Dia 1.

**⚠️ AD-008 revertido (2026-08-10) — ver AD-009 abaixo:** o commit AD-008
(integração real do pacote `agent_framework`) foi revertido porque um dev do
time (`gbezerra-ciandt`) já havia ramificado e implementado 3 das 4 fatias
(`agent/prompt.py`, `agent/judge.py`, `agent/guardrails/`) a partir da versão
**anterior** ao AD-008, sem o framework real integrado. Manter o AD-008 na
`main` bloquearia o merge desse trabalho com conflitos de reintegração
manual. **Estado atual do código:** não há mais dependência do
`agent_framework`/`agent-platform-oci` real em nenhum módulo — `agent/`,
`gateway/`, `orchestrator/` voltaram a usar apenas bibliotecas genéricas
(LangGraph, FastAPI, OpenAI client, OpenTelemetry local), como estavam antes
de 2026-08-07. `docs/ARQUITETURA.md` e `requirements.txt` já refletem essa
reversão — não citam mais o framework como dependência instalada.

**Achados ainda válidos do double-check de 2026-08-10 (anteriores ao revert):**
1. **Atraso de cronograma:** o Checkpoint 1 (`docs/PROPOSTA-POC.md`, Dia 5 —
   "ingestão + RAG funcionando ponta a ponta") já deveria ter ocorrido (repo
   criado 2026-08-04; hoje é o Dia 7 de um cronograma de 10 dias úteis), mas
   os 5 módulos de `rag_pipeline/` continuam com `NotImplementedError`
   (`chunker.py`, `vectorizer.py` [3x], `extractor.py`,
   `metadata_enricher.py`, `query_api.py`). **Continua em aberto** — é
   trabalho normal de implementação do time, não um bug a corrigir.
2. **Coordenação entre branches:** além da branch do `gbezerra-ciandt`
   (`test_new_branch`), surgiu uma segunda branch (`backend`, de `Kirllen`)
   também divergente da `main` antes do revert. **Atualização 2026-08-11:**
   `backend` foi mesclada na `main` via PR #1 (commit `c43df2d`) —
   implementa `gateway/channel_gateway.py::normalize()` e
   `orchestrator/graph.py::run_interaction()` (este último com resposta
   simulada hardcoded, ainda sem grafo LangGraph real) e liga o endpoint
   `/agent/interact` ponta-a-ponta. `test_new_branch` (`gbezerra-ciandt`)
   **continua sem PR aberto**, com 4 commits divergentes (`agent/prompt.py`,
   `agent/judge.py`, `agent/guardrails/input_guardrail.py`,
   `agent/guardrails/output_guardrail.py`) — é a próxima pendência de merge.
   O CI de `main` segue vermelho após o merge do PR #1 (14 failed / 5
   passed) — falha pré-existente e herdada (guardrails/judge/rag_pipeline
   ainda em `NotImplementedError`), não uma regressão introduzida pelo merge.

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

### AD-009: Reverter AD-008 — integração real do `agent_framework` desfeita (2026-08-10)

**Decision:** Reverter o commit `3e80828` (AD-008) na `main`, retirando a
dependência do pacote `agent_framework` real (instalado via
`pip install git+...`) de `agent/`, `gateway/`, `orchestrator/`,
`requirements.txt`, `Dockerfile` e `.env.example`. O código volta a usar
apenas bibliotecas genéricas (LangGraph, FastAPI, cliente OpenAI padrão,
OpenTelemetry local) — o estado anterior a 2026-08-07.
**Reason:** Um dev do time (`gbezerra-ciandt`) já havia ramificado a partir
do commit anterior ao AD-008 (`f2fc66f`) e implementado de facto 3 das 4
fatias do esqueleto (`agent/prompt.py`, `agent/judge.py`,
`agent/guardrails/input_guardrail.py`, `agent/guardrails/output_guardrail.py`)
sem o framework real integrado. Sem o revert, mesclar esse trabalho exigiria
reintegrar manualmente o `agent_framework` real em cima do código dele —
custo desproporcional para uma PoC de 2 semanas, dado que o objetivo central
da PoC (validar a viabilidade arquitetural do framework) pode ser retomado
depois, sem descartar o trabalho já implementado pelo time.
**Impact:** o achado do judge panel que motivou o AD-008 (nenhum módulo
integrava de fato o `agent_platform_oci`) volta a ser verdade — está
novamente registrado como risco aberto, não resolvido. Se a integração real
for retomada depois, refazer sobre o código já implementado pelo time
(não voltar a repetir o AD-008 do zero), para não gerar um terceiro
ciclo de revert.
**Resolution:** aberto — decidir com o time quando/se reintroduzir a
integração real do framework, agora que as fatias de `agent/` já têm
implementação própria em andamento.

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

- [x] AD-009: reverter AD-008 para destravar merge do trabalho já em
  andamento sobre a base sem o framework real — 2026-08-10.
- [x] Mesclar `backend` (`Kirllen`) na `main` — feito via PR #1
  (commit `c43df2d`), 2026-08-11.
- [ ] Mesclar `test_new_branch` (`gbezerra-ciandt`) na `main` — ainda sem
  PR aberto; revisar se corrige as 5 falhas de `tests/test_agent.py`
  hoje vermelhas em `main` por `NotImplementedError` em
  `agent/guardrails/`, `agent/prompt.py`, `agent/judge.py`.
- [ ] Concluir as 4 fatias de implementação (Data Engineer, AI Scientist,
  Backend/Integração, AI Developer Sr) — ver `docs/PAPEIS-E-ENTREGAVEIS.md`
- [ ] **Checkpoint 1 (Dia 5): ATRASADO** — ingestão + RAG ainda não
  funciona ponta a ponta (5 módulos de `rag_pipeline/` seguem com
  `NotImplementedError` em 2026-08-10, Dia 7 do cronograma de 10 dias)
- [ ] Checkpoint 2 (Dia 9): primeira demo end-to-end via `docker-compose up`
- [ ] Demo final + relatório de achados técnicos (1-2 páginas) sobre o
  `agent_platform_oci` — ver `docs/PROPOSTA-POC.md`, seção 10
