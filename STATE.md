# State

**Last Updated:** 2026-08-19
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
   `/agent/interact` ponta-a-ponta. O CI de `main` segue vermelho após o
   merge do PR #1 (14 failed / 5 passed) — falha pré-existente e herdada
   (guardrails/judge/rag_pipeline ainda em `NotImplementedError`), não uma
   regressão introduzida pelo merge. **Atualização 2026-08-17 (20:11):** PR
   #4 foi mesclado (commit `3013509`) após resolução do conflito de
   `.gitignore` (B-008, ver abaixo). **Nenhum módulo do projeto tem mais
   `NotImplementedError`** — as 4 fatias (Data Engineer, AI Scientist,
   Backend/Integração, e a integração hardcoded do AI Developer Sr) estão
   implementadas. CI do merge (run `32064471059`) mostra a suíte de testes
   100% verde (37 passed, 0 failed) — mas o *job* de lint segue vermelho por
   um erro pré-existente não relacionado ao PR #4: `mock_services/agents/cancellation.py:16`
   (variável local `msg` atribuída e nunca usada, `ruff F841`, introduzida no
   commit `e93b1bb` da branch `backend`). Trivial de corrigir, mas é o único
   motivo do CI de `main` ainda aparecer como `failure`.

**Atualização 2026-08-19 — PR #6 mesclada com CI ainda vermelho; este
`STATE.md` estava desatualizado:** a PR #6 (`feature/orchestrator-agentframework-native`
→ `main`, ver B-007) foi mesclada em `main` às 15:01 (commit `3be8bc1`), mas
nenhuma das 3 pendências que a própria B-007 listava como bloqueadoras do
merge foi resolvida antes disso — o CI do commit de merge (run
`32267586274`) segue `failure` pelo mesmo motivo já registrado
(`ResolutionImpossible`: `chainlit>=2.0.0` exige `fastapi>=0.115.3,<0.116`,
mas `requirements.txt` fixa `fastapi==0.115.0`), com o job de lint falhando
pelo mesmo erro e o build Docker sempre `skipped`. Isso viola diretamente o
critério §7 de `docs/CRITERIOS-DE-ACEITE.md` ("último push na branch
principal mostra pipeline verde"). Além disso, a versão deste `STATE.md`
anterior a esta atualização ainda descrevia a PR #6 como **aberta** —
desatualizada em relação ao GitHub real (já mesclada) no momento em que foi
escrita.

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

### B-007: Branch `feature/orchestrator-agentframework-native` reintroduz `agent_framework` sem coordenação com o AD-009 — CI quebrado (2026-08-17)

**Discovered:** 2026-08-17, via `gh run list`/`gh run view` no repositório
GitHub (`miltonabdon-arch/poc-agentic-chat`). Push de hoje (11:10, autor
`Igor Scaglia`) na branch `feature/orchestrator-agentframework-native`
(commit "feat(orchestrator): implementa build_graph + tracer + gateway
async com agent_framework nativo") adiciona em
`gateway/channel_gateway.py` o import `from agent_framework.channels.base
import ChannelMessage` — exatamente a dependência que o **AD-009**
(2026-08-10) havia removido deliberadamente da `main` para destravar o
merge do trabalho de `gbezerra-ciandt` e `Kirllen`. O pacote não foi
adicionado a `requirements.txt` nesta branch, então o CI quebra na etapa de
testes com `ModuleNotFoundError: No module named 'agent_framework'` (run
`32038179096`, job "Testes (unitários — sem dependência de LLM)").
**Impact:** se mesclada como está, a branch reabre o mesmo problema que o
AD-009 fechou (dependência real do framework não instalada/reprodutível) e
adiciona uma segunda linha de trabalho divergente sobre o mesmo ponto de
decisão, sem que isso conste em nenhum registro do time até agora. CI
vermelho nesta branch bloqueia merge para `main` enquanto não resolvido.
**Workaround:** nenhum — a branch não tem PR aberto ainda; nenhum código de
`main` foi afetado.
**Resolution:** decidir com o time (idealmente antes de abrir PR): (1) se a
intenção é reintroduzir a integração real do `agent_framework` de propósito
(reabrindo o que o AD-009 fechou), adicionar a dependência a
`requirements.txt`/`Dockerfile` corretamente e registrar isso como um novo
AD- explícito (não silenciosamente); ou (2) se foi um import acidental
(cópia de código de uma versão anterior ao revert), remover o import e
usar apenas as bibliotecas genéricas já padronizadas pelo AD-009.

**Atualização 2026-08-17 (12:29), commit `3d96b09`:** o mesmo autor
(`Igor Scaglia`) fez um novo push na branch — "fix: integração Flow
LiteLLM + correções de assinatura do RAG" — cuja mensagem afirma "Demo
ponta a ponta validado com Flow gpt-4o-mini: RAG, not_found, PII masking,
handoff fallback - todos funcionando", indicando que o autor trata a
integração do `agent_framework` como intencional e funcional (não um
import acidental). Apesar disso, `requirements.txt` **continua sem**
`agent_framework`, e o CI deste commit (run `32042764665`) segue
vermelho com o mesmo `ModuleNotFoundError: No module named
'agent_framework'` (2 erros de coleta em `tests/test_gateway.py` e
`tests/test_integracao.py`), mais 5 erros novos de lint (`E402` em
`scripts/run_demo.py`, import fora do topo do arquivo). Isso reforça a
hipótese (1) da Resolution acima — decisão intencional ainda não
formalizada como AD- — mas não resolve o CI quebrado nem cria PR. B-007
**continua em aberto**, sem PR.

**Atualização 2026-08-18 (19:04) — PR #6 aberta:** `Igor Scaglia` abriu a
PR #6 ("Feature/orchestrator agentframework native",
`feature/orchestrator-agentframework-native` → `main`), sem descrição
preenchida. Nesse momento a branch tinha 3 commits a mais que a análise
anterior (`82c2cc8` docs `ACHADOS-TECNICOS.md`/roteiro, `93a7741` correções
de ensaio, `17847d3` UI Chainlit com SSE em `/trace`) e estava desatualizada
desde o merge-base `420e8b5` (14/08) — **sete arquivos com conflito real**
de merge contra `main` (`.gitignore`, `agent/guardrails/output_guardrail.py`,
`agent/judge.py`, `agent/llm_client.py`, `agent/prompt.py`, `gateway/app.py`,
`tests/test_agent.py`). Os conflitos em `judge.py` e `output_guardrail.py`
não eram triviais: a branch carregava uma implementação **anterior e mais
fraca** desses módulos (regex único sem preservação de conteúdo em
`output_guardrail.py`, marcador fixo de string em vez do regex
`_NOT_FOUND_RE` em `judge.py`) e faltavam 4 testes já existentes em `main`
(`test_output_guardrail_limpa_negrito_preservando_nome_do_plano` e
análogos para link/cabeçalho/lista) — um merge ingênuo teria revertido
funcionalidade já validada por outro papel do time. Além disso, o
`STATE.md` próprio dessa branch (com `AD-010` registrando o vendoring do
`agent_framework` como concluído, "CI: ruff ✓ → pytest ✓ → docker build ✓",
"Nenhum blocker ativo") **contradizia a realidade do GitHub Actions**: os 3
runs de CI da branch até então (`32038179096`, `32042764665`,
`32173644419`) eram todos `FAILURE`. O run mais recente (`32173644419`,
pós-commit `17847d3`) tinha um segundo motivo de falha, novo e adicional ao
`ModuleNotFoundError: No module named 'agent_framework'`: o commit
adicionou `chainlit>=2.0.0` ao `requirements.txt`, que exige
`fastapi<0.116,>=0.115.3` — incompatível com `fastapi==0.115.0` já fixado
no projeto, gerando `ResolutionImpossible` no `pip install` (quebra antes
de lint/testes rodarem).

**Atualização 2026-08-18 (21:37) — rebase resolve os conflitos de merge,
mas não o CI:** `Igor Scaglia` fez force-push na branch (mesmas mensagens
de commit, hashes novos — ex.: `d070ef2` no lugar de `17847d3`), rebaseando
sobre o `main` atual (novo merge-base: `d1c07ce`, o HEAD de `main` no
momento). Confirmado via `git merge-tree`: **os 7 conflitos de arquivo
desapareceram** — `mergeable` passou de `CONFLICTING`/`DIRTY` para
`MERGEABLE`/`UNSTABLE`. O problema do `chainlit`/`fastapi` **persiste sem
alteração** (`requirements.txt` ainda tem `fastapi==0.115.0` e
`chainlit>=2.0.0` lado a lado) — os 2 novos runs de CI pós-rebase
(`32202545534`, `32202547601`, ambos 2026-08-19 00:47) continuam
`FAILURE` no `pip install`, com `Build imagem Docker` sempre `SKIPPED`
por dependência dos jobs anteriores.
**Resolution:** ainda aberto. Resolver antes do merge: (1) fixar uma
versão de `fastapi` compatível com `chainlit>=2.0.0` (`>=0.115.3,<0.116`)
ou remover a dependência do `chainlit` do `requirements.txt` principal se a
UI for opcional/experimental; (2) resolver a instalação do
`agent_framework` no CI de forma reprodutível — hoje só funciona em
execução local (o autor relata "29 testes unitários: 100% passando" e
"demo ponta a ponta validada" no `STATE.md`/`ACHADOS-TECNICOS.md` da
própria branch, mas isso não é verificável via pipeline, contrariando o
critério §7 de `docs/CRITERIOS-DE-ACEITE.md`); (3) confirmar que a UI
Chainlit (`/trace` SSE, `chainlit_app.py`, redirecionamento `:8080`) foi de
fato solicitada — não consta em `docs/PAPEIS-E-ENTREGAVEIS.md` nem em
`docs/CRITERIOS-DE-ACEITE.md`, e foi a causa direta da quebra de
dependências mais recente.

**Atualização 2026-08-19 — mesclada sem resolução:** confirmado via
`gh pr view 6` que a PR foi mesclada (`mergedAt: 2026-08-19T15:01:52Z`,
commit `3be8bc1`) sem que nenhum dos 3 itens de Resolution acima tivesse
sido endereçado. `requirements.txt` na `main` pós-merge continua com
`fastapi==0.115.0` e `chainlit>=2.0.0` lado a lado; não existe
`vendor/agent_framework/` no repositório (nem local, nem gerado por CI) — o
Dockerfile ainda faz `COPY vendor/agent_framework ...`, então mesmo o build
Docker (que nunca chega a rodar, pois é bloqueado por lint+testes) falharia
se lint/testes passassem. B-007 **continua aberto**, agora na `main` em vez
de numa branch.

---

### B-008: PR #4 (`test_new_branch` → `main`) passou a ter conflito de merge (2026-08-17)

**Discovered:** 2026-08-17, via `gh pr view 4` no repositório GitHub
(`miltonabdon-arch/poc-agentic-chat`). O PR #4 (aberto em 2026-08-14 por
`gbezerra-ciandt`, título "Add samples and mock ups for agents and sub
agents") recebeu 2 commits novos hoje — `8620fbe` ("ajuste no
gitignore", 17:11) e `4e47505` ("retira escopo tecnico", 17:40) — e o
GitHub agora reporta `mergeStateStatus: DIRTY` / `mergeable:
CONFLICTING`. Simulação local (`git merge-tree`) confirma que o único
conflito real está em `.gitignore`: a branch adiciona uma linha
`ESCOPO TÉCNICO.txt` na mesma posição em que `main` tem `.DS_Store` —
conflito trivial de uma linha, não estrutural.
**Impact:** o CI do PR também segue vermelho (9 failed / 27 passed) —
mas isso é esperado e não uma regressão nova: a branch está desatualizada
em relação a `main` desde `f2fc66f` (06/ago, merge-base), então não
incorpora nem o PR #1 (`gateway/channel_gateway.py::normalize()`
implementado) nem o PR #3 (`rag_pipeline/` implementado). As 9 falhas
(`tests/test_gateway.py`, `tests/test_ingestao.py`) são todas
`NotImplementedError` nesses módulos que já têm implementação real em
`main` — ou seja, um rebase/merge de `main` para dentro da branch
resolveria a maior parte do CI vermelho do PR, além do conflito de
`.gitignore`.
**Workaround:** nenhum aplicado ainda. O restante do conteúdo do PR
(fatias de AI Scientist: `agent/prompt.py`, `agent/judge.py`,
`agent/guardrails/`) não conflita com `main`.
**Resolution:** ✅ **Resolvido em 2026-08-17 (20:11).** `gbezerra-ciandt`
atualizou a branch com `main` (commit `70b3a49`, "Merge branch 'main' into
test_new_branch") antes de completar o merge do PR #4 (commit `3013509`).
Confirmado post-merge: suíte de testes 100% verde (37 passed, 0 failed,
run `32064471059`) — as 9 falhas por `NotImplementedError` desapareceram
como previsto. Resta apenas o erro de lint pré-existente
`mock_services/agents/cancellation.py:16` (não relacionado a este PR, ver
nota em "Current Work" acima).

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

## Lessons Learned (relevantes para esta PoC)

### L-001: `docs/ACHADOS-TECNICOS.md` cita SPEC errada para `ChannelMessage` e `EnterpriseRouter` (2026-08-19)

**Context:** verificação do achado #1 de `docs/ACHADOS-TECNICOS.md` ("O que
funcionou como esperado") contra o conteúdo real das SPECs em
`raw.githubusercontent.com/hoshikawa2/agent_platform_oci/main/specs/`,
seguindo a regra de nunca concluir por README/documento já escrito sem
reconferir a alegação pontual (ver regra de arquitetura em `.claude/CLAUDE.md`
do projeto principal).
**Problem:** O documento afirma "`ChannelMessage` (SPEC-003)" e
"`EnterpriseRouter` (SPEC-004)". Ambas as citações estão erradas: SPEC-003 é
"Agent-Gateway" (não menciona `ChannelMessage` — trata de sessão global e
roteamento entre backends multi-canal, sem citar essa classe) e SPEC-004 é
"MCP-Gateway" (roteamento de *tools* MCP — não menciona `EnterpriseRouter`
nem o módulo `agent_framework.routing`). Nenhuma SPEC nomeia
`EnterpriseRouter` explicitamente; a referência mais próxima é o
"Router Node" genérico do SPEC-002-Agent-Runtime. Em contraste,
`docs/ARQUITETURA.md` (mesmo repositório) já mapeia corretamente o Channel
Gateway → SPEC-009 — ou seja, a inconsistência é interna ao próprio
repositório da PoC, entre dois documentos que deveriam concordar.
**Impact:** `ACHADOS-TECNICOS.md` é o entregável formal do critério §9 de
`CRITERIOS-DE-ACEITE.md` e alimenta `docs/ROTEIRO-APRESENTACAO.md` — uma
citação de SPEC errada nesse documento pode se propagar para material de
apresentação à TIM/Oracle sem nova verificação.
**Resolution:** ✅ **Corrigido em 2026-08-19.** `docs/ACHADOS-TECNICOS.md`
atualizado — `ChannelMessage` agora citado como "relacionado ao SPEC-009",
sem SPEC própria nomeada; `EnterpriseRouter` agora citado como implementação
do "Router Node" genérico do SPEC-002, sem SPEC dedicado ao nome. Achado
propagado para o projeto principal em `.specs/project/STATE.md` (L-009).

### L-002: `AgentRuntimeMixin` está mapeado em `docs/ARQUITETURA.md` mas não é usado no código (2026-08-19)

**Context:** mesma verificação SPEC-a-SPEC, desta vez confirmando a linha
"`AgentRuntimeMixin` (via wrapper FastAPI) | SPEC-002 (Agent Runtime)" da
tabela de mapeamento em `docs/ARQUITETURA.md`.
**Problem:** `AgentRuntimeMixin` existe de fato no framework real
(`libs/agent_framework/src/agent_framework/runtime/agent_runtime.py`) — é um
mixin real com métodos como `build_messages()`, `_retrieve_rag_context()`,
`_call_mcp_tool()`, `_emit_ic/noc/grl()`. Porém `gateway/app.py` (o "wrapper
FastAPI" citado na tabela) não herda nem instancia essa classe — é um
`FastAPI()` puro com rotas implementadas do zero (`/agent/interact`,
`/trace`, `/health`, `/chat`). O mapeamento no documento de arquitetura é
mais otimista do que o código real: a PoC replica o *comportamento*
esperado do Agent Runtime, mas não usa a classe real do framework para
isso.
**Impact:** Diferente de `ChannelMessage`/`EnterpriseRouter`/`AgentObserver`
(que a PoC de fato integra), `AgentRuntimeMixin` é hoje só uma citação de
mapeamento — se isso for lido como "a PoC valida `AgentRuntimeMixin` na
prática", é uma conclusão não sustentada pelo código.
**Resolution:** ✅ **Corrigido em 2026-08-19.** Linha da tabela em
`docs/ARQUITETURA.md` qualificada — agora deixa explícito que
`gateway/app.py` não herda nem instancia a classe real `AgentRuntimeMixin`,
sendo um `FastAPI()` implementado do zero "inspirado na interface esperada".
Achado propagado para o projeto principal em `.specs/project/STATE.md`
(L-009).

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
- [x] Resolver B-008: atualizar PR #4 (`test_new_branch` → `main`) com
  merge de `main` e completar o merge — feito via commits `70b3a49` +
  PR #4 (commit `3013509`), 2026-08-17.
- [x] Concluir as 4 fatias de implementação (Data Engineer, AI Scientist,
  Backend/Integração, integração hardcoded do AI Developer Sr) — ver
  `docs/PAPEIS-E-ENTREGAVEIS.md`. Confirmado 2026-08-17: nenhum módulo
  com `NotImplementedError`, suíte de testes 100% verde.
- [ ] Corrigir lint pré-existente: `mock_services/agents/cancellation.py:16`
  (`ruff F841`, variável `msg` não usada) — único motivo do CI de `main`
  ainda aparecer vermelho após o merge do PR #4.
- [ ] Resolver B-007 — PR #6 foi **mesclada em `main` em 2026-08-19 (15:01,
  commit `3be8bc1`) sem resolução**: CI da `main` segue vermelho pelo mesmo
  `ResolutionImpossible` (`chainlit>=2.0.0` vs `fastapi==0.115.0`). Falta
  (a) resolver o conflito de dependência no `requirements.txt`, (b) tornar
  a instalação do `agent_framework` reprodutível no CI (hoje só funciona
  localmente via vendoring manual, e nem há `vendor/agent_framework/` no
  disco para o Dockerfile encontrar), (c) confirmar com o time se a UI
  Chainlit (`/trace`, `chainlit_app.py`) é escopo aprovado ou scope creep.
- [x] Corrigir citação de SPEC errada em `docs/ACHADOS-TECNICOS.md`
  (`ChannelMessage`/SPEC-003 e `EnterpriseRouter`/SPEC-004 — ver L-001) —
  corrigido em 2026-08-19.
- [x] Qualificar o mapeamento de `AgentRuntimeMixin` → SPEC-002 em
  `docs/ARQUITETURA.md` para deixar explícito que o código não herda a
  classe real (ver L-002) — corrigido em 2026-08-19.
- [x] **Checkpoint 1 (Dia 5):** atrasado no calendário original, mas
  tecnicamente concluído em 2026-08-17 — ingestão + RAG funcionando (todos
  os módulos de `rag_pipeline/` implementados, sem `NotImplementedError`).
- [ ] Checkpoint 2 (Dia 9): primeira demo end-to-end via `docker-compose up`
- [ ] Demo final + relatório de achados técnicos (1-2 páginas) sobre o
  `agent_platform_oci` — ver `docs/PROPOSTA-POC.md`, seção 10
