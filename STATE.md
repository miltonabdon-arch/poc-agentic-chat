# State

**Last Updated:** 2026-08-10
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

**⚠️ Double-check com múltiplos agentes (2026-08-10) — 2 achados abertos:**
1. **Atraso de cronograma não reconhecido até agora:** o Checkpoint 1
   (`docs/PROPOSTA-POC.md`, Dia 5 — "ingestão + RAG funcionando ponta a
   ponta") já deveria ter ocorrido (repo criado 2026-08-04; hoje é o Dia 7
   de um cronograma de 10 dias úteis), mas os 5 módulos de `rag_pipeline/`
   continuam com `NotImplementedError` (`chunker.py`, `vectorizer.py` [3x],
   `extractor.py`, `metadata_enricher.py`, `query_api.py`). Nenhuma nota
   anterior deste arquivo registrava esse atraso.
2. **CI estava vermelho, não verde** (contradizendo `docs/CRITERIOS-DE-ACEITE.md`,
   item 7): os 3 últimos runs de GitHub Actions falharam, incluindo o do
   próprio commit AD-008 (2026-08-07) — `gh run list` confirma
   `completed failure` em 2026-08-05, 2026-08-06 (job cancelado por timeout)
   e 2026-08-07. A causa raiz confirmada no run de 2026-08-07: (a) job
   `Lint` — 3 erros reais `E402` em `gateway/app.py:20-22`, introduzidos
   pelo próprio commit AD-008 ao mover `load_dotenv()` antes dos imports
   sem `# noqa` (corrigido nesta sessão); (b) job `Testes` — 7 de 18 testes
   falham por `NotImplementedError` em `rag_pipeline/` (esperado, é o
   esqueleto RAG ainda não implementado pelo time — não é regressão do
   AD-008). **O item 1 (atraso) continua em aberto**, é trabalho normal de
   implementação do time, não um bug a corrigir.

**Achado adicional (double-check, não bloqueante):** o componente mais
central da arquitetura para sustentar a tese "isso é uma integração real
do `agent_platform_oci`" é o Router/orquestrador (`orchestrator/graph.py`)
— e ele continua sendo um `StateGraph` próprio (LangGraph genérico), sem
usar o `AgentRuntimeMixin`/Router real do framework (a própria tabela em
`docs/ARQUITETURA.md` já documentava isso como decisão deliberada, não
como lacuna escondida). AD-008 integrou de fato 4 componentes periféricos
(PII, LLM client, contrato de canal, tracer) — confirmado por leitura do
código real do framework upstream — mas o núcleo de orquestração e o
judge (`agent/judge.py`) seguem sendo implementação própria. Isso não
invalida o AD-008 (a tabela nunca alegou "Real" para esses dois), mas
qualifica a alegação de `docs/PROPOSTA-POC.md` (seção 3) de que o risco
técnico remanescente é "apenas divergência de instância OCI real" — o
risco de composição com o Router/Runtime real do framework, fora do
template oficial, continua não testado por esta PoC.

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

- [ ] Concluir as 4 fatias de implementação (Data Engineer, AI Scientist,
  Backend/Integração, AI Developer Sr) — ver `docs/PAPEIS-E-ENTREGAVEIS.md`
- [ ] **Checkpoint 1 (Dia 5): ATRASADO** — ingestão + RAG ainda não
  funciona ponta a ponta (5 módulos de `rag_pipeline/` seguem com
  `NotImplementedError` em 2026-08-10, Dia 7 do cronograma de 10 dias)
- [ ] Checkpoint 2 (Dia 9): primeira demo end-to-end via `docker-compose up`
- [ ] Demo final + relatório de achados técnicos (1-2 páginas) sobre o
  `agent_platform_oci` — ver `docs/PROPOSTA-POC.md`, seção 10
