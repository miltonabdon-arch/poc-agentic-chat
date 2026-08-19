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

**Atualização 2026-08-19 (mais tarde) — item (1) resolvido, mas destampou
um segundo conflito pré-existente:** subir `fastapi` para `0.115.5`
(dentro da faixa `>=0.115.3,<0.116` exigida por `chainlit`) foi
insuficiente sozinho — validação em container limpo `python:3.12-slim`
(mesma versão do CI) revelou um **segundo** `ResolutionImpossible`
independente, mascarado até então porque o `pip` falhava antes de chegar
nele: `chainlit` depende de `traceloop-sdk`, que exige
`opentelemetry-api>=1.28.0`, mas `requirements.txt` fixava
`opentelemetry-api==1.27.0` (e `opentelemetry-sdk==1.27.0` exigia
`opentelemetry-api==1.27.0` exato). ✅ **Corrigido**: as 4 libs
OpenTelemetry (`opentelemetry-api`, `opentelemetry-sdk`,
`opentelemetry-exporter-otlp-proto-grpc`,
`opentelemetry-exporter-otlp-proto-common`) subidas juntas de `1.27.0` para
`1.29.0` (versão que satisfaz `traceloop-sdk` e mantém as 4 libs em
lockstep, como já eram). Validado com `pip install --dry-run` e depois
`pip install` real (sem `--dry-run`) em `python:3.12-slim` — instalação
completa sem erro, `import fastapi, chainlit, opentelemetry.sdk, langgraph,
chromadb` funciona (`fastapi==0.115.5`, `chainlit==2.6.3` resolvido). Item
(1) da Resolution original agora está de fato resolvido — restam (2)
vendoring reprodutível do `agent_framework` e (3) confirmação de escopo da
UI Chainlit (mantida no escopo por decisão do usuário, 2026-08-19).
**Lição:** ao corrigir um conflito de dependência, sempre revalidar com
`pip install --dry-run` (ou instalação real) num ambiente limpo com a
mesma versão de Python do CI antes de considerar resolvido — corrigir só o
sintoma reportado no log de erro pode deixar um segundo conflito
mascarado atrás do primeiro.

**Atualização 2026-08-19 (confirmação via CI real, run `32295668099`):**
push do commit `3a3a6f4` confirma no GitHub Actions exatamente o previsto —
job **Lint: ✅ passou** (antes falhava no mesmo `pip install`); job
**Testes: ainda falha**, mas agora por um motivo diferente e já esperado —
`ModuleNotFoundError: No module named 'agent_framework'` em
`tests/test_gateway.py` e `tests/test_integracao.py` (via
`gateway/channel_gateway.py:8`), exatamente o item (b) já registrado
(vendoring do `agent_framework` não é reproduzível no CI — não existe
`vendor/agent_framework/` no repositório nem passo de CI que o gere). Job
**Build Docker: skipped** (depende de Lint+Testes). Confirma que o item
(a) está 100% resolvido e isola definitivamente o item (b) como o único
bloqueador restante do CI.

**Atualização 2026-08-19 (item b resolvido) — instalação do `agent_framework`
via `git+https` pinado, opção D das 4 avaliadas:** antes de implementar,
foram avaliadas 4 opções: (A) `pip install git+.../#subdirectory=libs/
agent_framework` sem pin, (B) índice PyPI interno, (C) vendorizar como
artefato versionado no repo da PoC, (D) passo dedicado no CI/Dockerfile
que instala direto do GitHub, pinado num commit. B foi descartada (exige
infra fora do escopo de 2 semanas); C foi descartada (versionaria código
de terceiros no repo da PoC, questão de proveniência/licenciamento); A
tinha 2 problemas próprios: `libs/agent_framework/pyproject.toml` real
exige `langgraph>=0.2.60`, mas a PoC fixa `langgraph==0.2.34` (conflito
novo), e instalar o pacote completo (`pip install` sem `--no-deps`) puxaria
`oracledb`, `oci`, `pymongo`, `redis`, `motor`, `google-cloud-pubsub`,
`mcp`, `langfuse` — todas as 29 dependências do `pyproject.toml`, mesmo a
PoC usando só 3 submódulos (`channels`, `routing`, `observability`).
Confirmado por leitura do código-fonte real (`channels/base.py`,
`routing/enterprise_router.py`, `observability/observer.py`, e toda a
cadeia de imports que eles tocam — `analytics/*`, `routing/continuity.py`,
`routing/config_loader.py`, `cache/cache.py`) que nenhum desses módulos
importa as dependências pesadas no nível de topo (tudo lazy-loaded dentro
de métodos/`__init__`) — logo `pip install --no-deps` é seguro e evita
tanto o conflito de `langgraph` quanto o peso das dependências.
**Implementado (opção D):** `.github/workflows/ci.yml` (jobs `lint` e
`test`) e `Dockerfile` agora rodam
`pip install --no-deps "git+https://github.com/hoshikawa2/agent_platform_oci.git@<commit>#subdirectory=libs/agent_framework"`
logo após `pip install -r requirements.txt`, pinado no commit
`f9c66b4792ac9fd63d7397dbab3bcac310e4d780` (HEAD do upstream em
2026-08-19) via `env.AGENT_FRAMEWORK_REF` no CI e `ARG
AGENT_FRAMEWORK_REF` no Dockerfile — mesmo valor nos dois lugares, fácil de
atualizar junto no futuro. `Dockerfile` ganhou `apt-get install git` (necessário
para o `pip install git+https`). `vendor/` removido do `.gitignore` (não é
mais usado) e `README.md` (Quick start) atualizado com o novo comando de
instalação.
**Validado localmente antes do commit:** (1) `docker build` completo da
imagem passou sem erro, incluindo o passo do `agent_framework`; (2) dentro
da imagem final, `from agent_framework.channels.base import ChannelMessage`,
`EnterpriseRouter`, `AgentObserver`, e os módulos reais da PoC
(`gateway/channel_gateway.py`, `orchestrator/tracer.py`, já com a correção
do B-009) importam sem erro. **Não foi possível** validar `pytest` completo
dentro do Docker local (VM do Docker Desktop com só ~3.8GB de RAM disponível
— processo morto por OOM ao carregar `torch`/`transformers`/
`sentence-transformers` da suíte de testes); essa validação fica para o CI
real do GitHub Actions, que tem recursos adequados.
**Resolution:** aberto até o próximo push confirmar o job de Testes verde
no GitHub Actions (runner com memória suficiente, diferente do Docker
local). Se passar, falta só decidir se o commit pinado do `agent_framework`
deve ser atualizado periodicamente (nenhum processo automático disso hoje).

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

### B-009: `orchestrator/tracer.py` chama `AgentObserver.emit()` diretamente com `event_type` sem prefixo — Camada 1 (framework) nunca dispara na prática (2026-08-19)

**Discovered:** 2026-08-19, ao ler o código-fonte real de
`agent_framework.observability.observer.AgentObserver` (não só a SPEC-007)
para validar a aderência da PoC, comparando com `orchestrator/tracer.py`.
**Problem:** `trace_interaction()` em `orchestrator/tracer.py:56` chama
`await _observer.emit(event_type=event_type, payload=dados)` com
`event_type` igual a `"IC"`, `"NOC"` ou `"GRL"` (sem ponto). O `emit()` real
do framework decide se um evento é NOC (e portanto se deve chamar
`emit_noc_event()`, o publisher OTEL/NOC real) assim:
`is_noc = str(event_type).startswith("NOC.") or metadata.get("noc") is True`.
Como `"NOC"` não começa com `"NOC."` e a PoC nunca passa
`metadata={"noc": True}` (isso só acontece dentro de `emit_noc()`, que a
PoC não usa), `emit_noc_event()` nunca é chamado — o mesmo vale para
`"IC"`/`"GRL"` via `_apply_control_defaults()`. Diferente de L-001/L-002
(erros de citação/mapeamento em documentação), este é um **bug funcional no
código**: a "Camada 1: framework (noop local, real em OCI)" que o próprio
docstring de `tracer.py` descreve como ativa nunca dispara de fato — só as
Camadas 2 (log local) e 3 (broadcaster SSE/Chainlit) produzem qualquer
efeito observável. O framework já resolve isso com os métodos
especializados `emit_ic(code, ...)`, `emit_noc(code, ...)`,
`emit_grl(code, ...)`, que a PoC não usa.
**Impact:** Nenhum caso de teste/demo detectou isso porque a Camada 2 (log
local) mascara o problema — ela sempre imprime a linha `TRACE|tipo|...`
independente do que a Camada 1 faz. O critério §6 de
`CRITERIOS-DE-ACEITE.md` ("observabilidade") passa mesmo com a integração
real do framework quebrada, porque o critério nunca checou a Camada 1
isoladamente.
**Workaround:** nenhum aplicado — a Camada 2 (log local) e Camada 3
(broadcaster) continuam funcionando normalmente, então a demo não é afetada
visualmente, só a integração real com o framework fica sem efeito.
**Resolution:** ✅ **Corrigido em 2026-08-19.** `orchestrator/tracer.py`
agora despacha para `_observer.emit_ic()`/`emit_noc()`/`emit_grl()` via um
dicionário `_EMIT_METHODS` (chave `event_type` → nome do método), em vez de
chamar `_observer.emit(event_type=...)` diretamente. A Camada 1 do
framework passa a marcar corretamente `metadata={"ic"|"noc"|"grl": True}`
e disparar `emit_noc_event()` quando aplicável. Nenhuma mudança na
assinatura pública de `trace_interaction()` nem no formato de log/broadcaster
(Camadas 2 e 3) — apenas a chamada interna ao `AgentObserver` foi corrigida.
Suíte de testes não pôde ser executada neste ambiente (`pytest_bdd`/deps do
projeto ausentes localmente), mas os testes existentes de observabilidade
(`tests/step_defs/test_bdd_6.py`) só verificam Camadas 2/3, que não foram
alteradas — validado apenas por leitura sintática (`ast.parse`) e revisão
manual.

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

### L-003: Tabela de aderência ponto a ponto contra o `agent_framework` real — 3 módulos reinventados, 1 bug corrigido (B-009), 3 já corretos (2026-08-19)

**Context:** consolidação final da avaliação de aderência desta PoC contra
o código-fonte real do framework (não só as SPECs), cobrindo todos os
componentes citados em `docs/ARQUITETURA.md`. Complementa L-001/L-002
(erros de documentação) e B-009 (bug de código já corrigido) com uma visão
única de "o que já está certo" vs. "o que ainda reinventa algo que o
framework já entrega pronto".
**Tabela de aderência:**

| Componente da PoC | Módulo/classe real do `agent_framework` | Status | Ação |
|---|---|---|---|
| `ChannelMessage` (`gateway/models.py`, `channel_gateway.py`, `orchestrator/graph.py`, `tracer.py`) | `agent_framework.channels.base.ChannelMessage` | ✅ Aderente | Nenhuma |
| Roteamento por intenção (`orchestrator/graph.py` + `routing_config.yaml`) | `agent_framework.routing.enterprise_router.EnterpriseRouter` | ✅ Aderente (schema do YAML bate com `IntentDefinition`/`RouterStatePolicy` reais) | Nenhuma |
| Emissão de eventos IC/NOC/GRL (`orchestrator/tracer.py`) | `agent_framework.observability.observer.AgentObserver` | ✅ Corrigido (era B-009 — usava `emit()` bruto em vez de `emit_ic/noc/grl()`) | Nenhuma |
| Normalização de entrada (`gateway/channel_gateway.py::normalize()`) | `agent_framework.channels.gateway.ChannelGateway.normalize(channel, payload) -> ChannelMessage` | ❌ Reinventado — monta `ChannelMessage` manualmente em vez de instanciar a classe real | Trocar por `ChannelGateway().normalize(...)` |
| Guardrails input/output (`agent/guardrails/`, `agent/models.py`) | `agent_framework.guardrails.pipeline.GuardrailPipeline` (`run_input`/`run_output`, retorno `RailResult`/`RailAction`) | ❌ Reinventado — vocabulário próprio (`GuardrailResult`/`Violation`/`Action`) diverge do real (`RailAction: allow, sanitize, retry, block, handover, observe`) | Migrar para `GuardrailPipeline`; PII já tem `PiiMaskRail`/`OutputPiiMaskRail` prontos; "fora de domínio" tem `OutOfScopeRail` pronto |
| Menção a concorrente (regra própria da TIM) | `agent_framework.guardrails.custom_rails.CustomRails` (mecanismo de extensão) | ⚠️ Lógica própria correta, mas não plugada no pipeline do framework | Registrar via `CustomRails.add(MeuRail(), stage="input")` dentro do `GuardrailPipeline`, em vez de função solta |
| Judge offline (`agent/judge.py`) | `agent_framework.judges.judge.JudgePipeline` (`GroundednessJudge`, `ResponseQualityJudge` prontos) | ❌ Reinventado — 2 dos 3 proxies ad-hoc já têm judge determinístico equivalente pronto | Migrar para `JudgePipeline` via `judges.yaml`; manter só `not_found_consistency` como extensão custom, se necessário |
| Runtime FastAPI (`gateway/app.py`) | `agent_framework.runtime.agent_runtime.AgentRuntimeMixin` | ❌ Não integrado — `FastAPI()` puro, não herda o mixin (ver L-002) | Avaliar se cabe no escopo da PoC — mixin é mais amplo (RAG, MCP tools, cache LLM); pode ser simplificação deliberada aceitável, diferente dos itens acima |

**Impact:** dos 8 componentes mapeados em `docs/ARQUITETURA.md`, 3 estão
totalmente aderentes, 1 tinha um bug de integração já corrigido (B-009), e
3 reinventam com vocabulário/contrato próprio algo que o framework já
entrega pronto (guardrails, judge, channel gateway) — o mesmo padrão do
gap de nomenclatura já visto em L-008 do projeto principal, mas agora em
código funcional, não só em diagramas/design. `AgentRuntimeMixin` é o único
item onde a simplificação pode ser aceitável dado o escopo de 2 semanas
(mixin cobre muito mais que um wrapper HTTP simples).
**Resolution:** aberto — decisão do time sobre migrar os 3 itens ❌ antes do
fim da PoC ou registrar como Deferred Idea (ver Todos abaixo). A migração
mais simples e isolada é `ChannelGateway.normalize()` (troca direta de uma
função); guardrails e judge exigem realinhar os contratos de dados
(`GuardrailResult`/`Violation`/`Action` → `RailResult`/`RailAction`) usados
em `orchestrator/graph.py` e nos testes.
**Prevents:** Tratar "a PoC integra o `agent_framework`" como afirmação
binária — a integração é parcial e desigual entre componentes; qualquer
nova alegação de aderência deve apontar para esta tabela em vez de
generalizar a partir de só os componentes já corretos.

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
- [x] Resolver item (a) de B-007 — conflito de dependência no
  `requirements.txt` (`fastapi`×`chainlit` e, depois de corrigido esse,
  `opentelemetry-api`×`traceloop-sdk` via `chainlit`). Corrigido em
  2026-08-19: `fastapi` → `0.115.5`, família `opentelemetry-*` → `1.29.0`.
  Validado com `pip install` real em `python:3.12-slim`.
- [x] Resolver item (b) de B-007 — `agent_framework` agora instalado via
  `pip install --no-deps git+https://...@<commit>` (pinado), no CI e no
  Dockerfile, em vez de vendoring manual. Corrigido em 2026-08-19; (c) já
  confirmado que a UI Chainlit fica no escopo (decisão do usuário,
  2026-08-19).
- [ ] Confirmar no GitHub Actions (push após 2026-08-19) que o job de
  Testes fica verde com a instalação via `git+https` — validado localmente
  só até `docker build` + import dos módulos (não foi possível rodar
  `pytest` completo no Docker local por falta de memória, ver B-007).
- [x] Corrigir citação de SPEC errada em `docs/ACHADOS-TECNICOS.md`
  (`ChannelMessage`/SPEC-003 e `EnterpriseRouter`/SPEC-004 — ver L-001) —
  corrigido em 2026-08-19.
- [x] Qualificar o mapeamento de `AgentRuntimeMixin` → SPEC-002 em
  `docs/ARQUITETURA.md` para deixar explícito que o código não herda a
  classe real (ver L-002) — corrigido em 2026-08-19.
- [x] Corrigir B-009: trocar `_observer.emit(event_type=...)` por
  `emit_ic()`/`emit_noc()`/`emit_grl()` em `orchestrator/tracer.py` — a
  Camada 1 (framework real) hoje nunca dispara. Corrigido em 2026-08-19.
- [ ] Decidir e, se aprovado, migrar os 3 módulos reinventados listados na
  tabela de aderência do L-003: `gateway/channel_gateway.py::normalize()`
  → `ChannelGateway.normalize()`; `agent/guardrails/` → `GuardrailPipeline`;
  `agent/judge.py` → `JudgePipeline`. Se não entrar no escopo de 2 semanas
  desta PoC, registrar como Deferred Idea explícita.
- [x] **Checkpoint 1 (Dia 5):** atrasado no calendário original, mas
  tecnicamente concluído em 2026-08-17 — ingestão + RAG funcionando (todos
  os módulos de `rag_pipeline/` implementados, sem `NotImplementedError`).
- [ ] Checkpoint 2 (Dia 9): primeira demo end-to-end via `docker-compose up`
- [ ] Demo final + relatório de achados técnicos (1-2 páginas) sobre o
  `agent_platform_oci` — ver `docs/PROPOSTA-POC.md`, seção 10
