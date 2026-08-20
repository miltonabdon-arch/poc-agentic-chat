# Roteiro de Apresentação — Agente de Catálogo TIM (PoC)

**Data:** 2026-08-21 | **Apresentador:** Igor Scaglia (AI Developer Sr, CI&T)
**Duração estimada:** 25–30 minutos

---

## Fio condutor da apresentação

A narrativa percorre o arco completo de uma PoC colaborativa:

> **Hipótese** (PROPOSTA-POC §3) →
> **Contratos definidos** (kickoff) →
> **Cada papel entrega sua fatia** (paralelo) →
> **Conflitos encontrados e resolvidos** (integração) →
> **Grafo montado** (AI Dev Sr) →
> **Demo contra os critérios** (com observabilidade ao vivo) →
> **Achados e o que fica para o projeto real**

O ponto de chegada não é "olha o que eu fiz" — é "olha o que o framework
permite que o time construa, com papéis separados, em 2 semanas".

---

## Estrutura (com timing)

| # | Bloco | Tempo |
|---|-------|-------|
| 1 | Hipótese: por que essa PoC existe | 2 min |
| 2 | Contratos: a cola definida no kickoff | 3 min |
| 3 | O que cada colega entregou e como chegou até mim | 4 min |
| 4 | O que eu recebi e o que faltava: montar o grafo + observabilidade | 4 min |
| 5 | **DEMO AO VIVO** — 7 casos vs. os critérios de aceite | 8 min |
| 6 | BDD: como os critérios viraram testes executáveis | 2 min |
| 7 | Achados técnicos: o que fica para o projeto real | 3 min |
| 8 | Perguntas | livre |

---

## Preparação (antes de entrar na sala)

Executar nesta ordem — não durante a apresentação.

**1. Ingestão** (só se `chroma_data/` não existir ou estiver vazio)

VS Code → Run & Debug → **"Ingestão (run_ingestao.py)"** → F5.
Aguardar: `Ingestão concluída: 8 documentos, 32 chunks`.

**2. Subir infraestrutura** (mock-services + Langfuse + DB)

```powershell
docker compose --profile infra up -d
```

Aguardar todos os containers `healthy`:

```powershell
docker compose ps
# mock-services   healthy
# langfuse         healthy
# langfuse-db      healthy
```

**3. Subir a aplicação**

Via terminal (WSL):

```bash
make up
```

Aguardar todos os serviços ficarem `healthy` (`docker compose ps`).

> **Alternativa (modo local sem Docker):** VS Code → Run & Debug → **"Apresentação Completa"** → F5.

**4. Verificar saúde**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
# Retorno esperado: {"status":"ok"}
```

**5. Abrir as abas do browser (deixar prontas antes da sala)**

| Aba | URL | Para quê |
|-----|-----|----------|
| Tab 1 | `http://localhost:8080` | Chainlit — Chat + Steps ao vivo (Bloco 5) |
| Tab 2 | `http://localhost:3000` | Langfuse — dashboard de traces persistidos |

> Langfuse: login padrão `admin@langfuse.com` / `password` (configurado no `.env`).
> Se LANGFUSE_PUBLIC_KEY não estiver no `.env`, Langfuse fica desabilitado — o
> trace local e SSE continuam funcionando normalmente.

**6. Smoke test** (absorver warm-up E confirmar RAG)

Na **Tab 1 (Chainlit)**, digitar no chat:
```
Quais franquias de dados o Plano Turbo 40GB inclui?
```
Observar os steps aparecerem em tempo real com ícones por tipo de evento:
- 🗺️ GRAPH — topologia compilada e estado inicial do grafo
- ✅ NOC — roteamento via EnterpriseRouter (palavras-chave, sem LLM)
- 📊 STATE — δ do GraphState após cada nó
- ⚙️ FLOW — sub-componente entrou/saiu (rag.query, llm.complete, mock.*)
- 🔍 RAG — resultado da busca no catálogo
- 🤖 LLM — chamada ao modelo de linguagem
- 🎭 MOCK — chamada HTTP a mock_services
- ⚖️ JUDGE — avaliação de qualidade offline
- 🏁 ORCH — resultado executivo do pipeline
- 🛡️ GRL — guardrail ativado (só aparece quando bloqueado)

Aguardar os steps fecharem e verificar se a resposta menciona "40GB".

Se falhar: verificar logs no terminal integrado do VS Code antes de entrar na sala.

> **Atenção — warm-up do modelo:** a primeira requisição após subir o cluster
> demora 30–60s porque `paraphrase-multilingual-MiniLM-L12-v2` e
> `BAAI/bge-reranker-v2-m3` carregam pesos em memória na primeira chamada.
> **O smoke test (passo 6 acima) serve exatamente para absorver esse warm-up.**
> Nunca faça a primeira requisição ao vivo na frente da audiência.

---

## Bloco 1 — Hipótese: por que essa PoC existe (2 min)

**Abrir:** `docs/PROPOSTA-POC.md` → seção 3 (Hipótese a validar)

```
"É possível montar, em 2 semanas, um agente conversacional funcional
ponta a ponta sobre agent_platform_oci — com ingestão RAG própria,
guardrails de input/output, orquestração via grafo e observabilidade
nativa — usando apenas componentes locais/mock, sem depender de
provisionamento de infraestrutura OCI real."
```

**Fala sugerida:**
> "Antes desta PoC, a equipe confirmou que o `agent_platform_oci` é real e
> maduro — mas só lendo documentação. A questão era: quando a gente roda,
> o que funciona como previsto e o que exige adaptação?
> Essa pergunta virou a hipótese que vamos responder hoje."

**Pontos a marcar:**
- Não é código descartável — os contratos de dados vão para o projeto real
- Caso de uso deliberadamente simples para não travar no caso de uso, mas sim no framework
- LLM real (Flow CI&T) desde o Dia 13 — não é mock end-to-end

---

## Bloco 2 — Contratos: a cola definida no kickoff (3 min)

**Abrir:** `CLAUDE.md` → seção "Contratos de dados entre módulos" (tabela)

Mostrar os 3 contratos que o time acordou antes de escrever qualquer código:

| Contrato | Produtor | Consumidor | O que carrega |
|----------|----------|-----------|---------------|
| `QueryResult` | Ana (rag_pipeline) | Igor (orchestrator) | found, chunk_id, text, source_document_id, confidence_score |
| `GuardrailResult` | Gustavo (agent) | Igor (orchestrator) | guardrail_type, violation, action_taken, text |
| `ChannelMessage` | Kirllen (gateway) | Igor (orchestrator) | channel, session_id, user_id, text, context |

**Fala sugerida:**
> "O paper do framework fala em contratos de dados como 'cola' entre papéis.
> A gente levou isso a sério: nenhum dos quatro papéis começou a codificar
> antes de ter esses três contratos assinados.
> Se eu errar a integração, o problema está aqui — não no código de cada papel."

**Ponto visual:** mostrar `rag_pipeline/models.py` e `agent/models.py`
— são literalmente 2 arquivos de ~30 linhas cada que sustentam tudo.

---

## Bloco 3 — O que cada colega entregou e como chegou até mim (4 min)

**Fala sugerida:**
> "Cada papel desenvolveu sua fatia em branch separada.
> Vou contar o que cada um entregou e como isso chegou para mim."

### Ana (Data Engineer) — rag_pipeline/

- Branch: `main` (entregue via PR)
- Entregáveis: `extractor.py`, `chunker.py`, `metadata_enricher.py`, `vectorizer.py`, `query_api.py`
- O que veio pronto para eu usar: `query(client, text) → QueryResult`
- Achado inesperado que ela resolveu: embedding default do Chroma (inglês) não discriminava "Turbo 40GB" de "Controle 20GB" — ela escolheu `paraphrase-multilingual-MiniLM-L12-v2` + CrossEncoder re-ranking

**Mostrar (30 segundos):** `rag_pipeline/query_api.py` L55–89 — a função `query()` com CrossEncoder.

### Gustavo (AI Scientist) — agent/

- Branch: `test_new_branch` (cherry-pick manual — PR não foi aberto a tempo)
- Entregáveis: `prompt.py`, `guardrails/input_guardrail.py`, `guardrails/output_guardrail.py`, `judge.py`
- O que veio pronto: `build_prompt(question, query_result)`, `not_found_response()`, `build_crm_prompt(question, intent, api_data)`, `build_supervisor_prompt(question)`, `check_input(text)`, `check_output(text)`
- Ponto crítico: `build_prompt()` retorna `None` quando `found=False` — isso obrigou o grafo a nunca chamar o LLM para planos inexistentes

**Mostrar (30 segundos):** `agent/prompt.py` — o `if not query_result.found: return None`.

### Kirllen (Backend/Integração) — gateway/ + mock_services/

- Branch: `backend` (entregue via PR #1)
- Entregáveis: `channel_gateway.py`, `app.py`, `mock_services/` completo (CRM, cancellation, deals, plans)
- O que veio pronto: `normalize(raw_message) → ChannelMessage` e o runtime FastAPI
- Valor do mock_services: os handoffs de cancelamento e deals funcionam localmente sem nenhuma integração real
- **Novo:** middleware de logging em `mock_services/app.py` — cada requisição recebida emite `[MOCK] REQUEST` e `[MOCK] RESPONSE` com latência e conversation_id

**Mostrar (30 segundos):** `gateway/channel_gateway.py` — a função `normalize()` que cria o `ChannelMessage`.

---

## Bloco 4 — O que eu recebi e o que faltava: montar o grafo + observabilidade (4 min)

**Fala sugerida:**
> "Eu recebi três branches, três contratos implementados, e o `agent_framework`
> com `ChannelMessage`, `EnterpriseRouter` e `AgentObserver`.
> O framework não monta o grafo — essa é a responsabilidade explícita do AI Dev Sr.
> E para a demo funcionar ao vivo, precisei adicionar uma camada de observabilidade
> que tornasse o 'invisível' visível — em tempo real."

### O grafo (build_graph)

**Mostrar:** `orchestrator/graph.py` — o docstring com a tabela de atribuição:

```
Ana Carolina → QueryResult      (rag_pipeline/query_api.py)
Gustavo      → GuardrailResult  (agent/guardrails/, branch test_new_branch)
Kirllen      → ChannelMessage   (gateway/channel_gateway.py, branch backend)
Igor         → build_graph(), run_interaction()
```

**Mostrar:** `orchestrator/graph.py` função `build_graph()`:
- `g.add_node("input_guardrails", node_input_guardrails)` — código do Gustavo, nó do grafo de Igor
- `g.add_conditional_edges("input_guardrails", _after_guardrails)` — a lógica block/allow
- `g.set_entry_point("input_guardrails")` — sempre começa pelo guardrail, nunca pelo agente

**Estratégia por nó — nem todos chamam o LLM:**

| Nó | Estratégia |
|----|-----------|
| `input_guardrails` | Regex + regras — sem LLM |
| `routing_decision` | Keyword matching (`EnterpriseRouter`) — sem LLM |
| `catalog_agent` | RAG hit → `build_prompt` + LLM; RAG miss → `build_not_found_prompt` + LLM |
| `billing` | CRM mock + `build_crm_prompt` + LLM |
| `eligibility` | CRM mock + `build_crm_prompt` + LLM |
| `simulation` | CRM mock + `build_crm_prompt` + LLM |
| `supervisor` | `build_supervisor_prompt` + LLM (intenções fora dos domínios) |
| `handoff_cancellation` | HTTP → `mock_services` — **sem LLM** (agente externo responde) |
| `handoff_deals` | HTTP → `mock_services` — **sem LLM** (agente externo responde) |
| `output_guardrails` | Regex + regras — sem LLM |
| `judge` | `judge_batch()` + LLM — avaliação offline, não chega ao usuário |

**Fala:** *"Os dois handoffs são os únicos nós de domínio sem LLM — eles existem para passar o controle a outro agente. No sistema real, esse agente externo teria seu próprio LLM e seu próprio pipeline."*

### A observabilidade em 4 camadas

**Fala sugerida:**
> "O `AgentObserver` do framework existe, mas localmente ele não imprime nada —
> ele espera instâncias reais de OCI ou Langfuse. Para a demo funcionar, adicionei
> 3 camadas locais que se encaixam sem substituir a camada do framework."

**Mostrar:** `orchestrator/tracer.py` — o `NODE_OWNERS` dict:

```python
NODE_OWNERS = {
    "node.input_guardrails": "IGOR",   "node.catalog_agent": "IGOR",
    "rag.query": "ANA",                "rag.vectorizer": "ANA",
    "llm.complete": "GUSTAVO",         "guardrail.input": "GUSTAVO",
    "mock.crm": "KIRLLEN",             "mock.cancellation": "KIRLLEN",
    ...
}
```

**Fala:** *"Todo evento sabe quem é o dono — aparece nos logs estruturados e no Langfuse."*

**Mostrar:** `orchestrator/tracer.py` — função `trace_flow()`:

```python
async def trace_flow(subtype, component, channel_message, payload=None):
    # emite FLOW ENTER / FLOW EXIT para log + broadcaster SSE
```

**Camadas de observabilidade:**

| Camada | Onde aparece | Quando |
|--------|-------------|--------|
| 1. AgentObserver + Langfuse | `http://localhost:3000` | IC, NOC, GRL — framework events |
| 2. Log estruturado local | Terminal / stdout | `TRACE\|FLOW\|component=...\|owner=...` |
| 3. SSE broadcaster | Chainlit steps ao vivo | FLOW ENTER/EXIT em tempo real |
| 4. Langfuse self-hosted | `http://localhost:3000` | Traces persistidos com latência |

**Os 11 tipos de evento:**

| Sigla | Significado | Dono |
|-------|------------|------|
| `IC` | Interaction Created | Framework |
| `NOC` | Node Completed | Framework |
| `GRL` | GuaRaiL fired | Framework |
| `FLOW` | ENTER/EXIT por componente | trace_flow() |
| `LLM` | Chamada ao modelo | _call_llm_and_trace() |
| `RAG` | Busca no Chroma | node_catalog_agent |
| `MOCK` | HTTP call ao mock_services | helpers de handoff |
| `JUDGE` | Avaliação de qualidade offline | judge_batch() |
| `GRAPH` | Topologia compilada + estado inicial | run_interaction() |
| `ORCH` | Resultado executivo do pipeline | run_interaction() |
| `STATE` | δ do GraphState após cada nó | run_interaction() |

**Conflito que precisou resolver (AD-008 → AD-009 → AD-010):**
> "A primeira tentativa de integrar o `agent_framework` causou conflitos
> com as outras branches em andamento. Revertemos, esperamos as branches
> ficarem prontas, e reintroduzimos com instalação pinada via `pip install --no-deps git+https://...` — CI e Dockerfile usam o mesmo hash de commit, reprodutível em qualquer ambiente. 3 dias de custo,
> aprendizado real para o projeto."

---

## Bloco 5 — DEMO AO VIVO (8 min)

**Tela principal:** Tab 1 — `http://localhost:8080` (Chainlit)

> Os steps expansíveis à esquerda do Chainlit são o "debaixo do capô" da PoC:
> mostram em tempo real qual componente está em execução, com ícone por tipo
> de evento (🗺️ GRAPH · ✅ NOC · 📊 STATE · ⚙️ FLOW · 🔍 RAG · 🤖 LLM · 🎭 MOCK · ⚖️ JUDGE · 🏁 ORCH · 🛡️ GRL) e o
> input/output de cada etapa. O painel Langfuse (Tab 2) mostra os traces
> persistidos com latência acumulada.

### Casos e narrativa de cada um:

**[CASO 1/7] §3 — RAG: Franquia do Turbo 40GB**

Digitar no Chainlit:
```
Quais franquias de dados o Plano Turbo 40GB inclui?
```
- Enquanto o pipeline roda: observar steps aparecendo com ícones por tipo
- Steps esperados em ordem: 🗺️ `GRAPH` → 📊 `STATE` → `✅ rota → catalog_agent · intenção: catalog` → 📊 `STATE` → ⚙️ `rag.query` → 🔍 `RAG ✓ turbo-40gb` → ⚙️ `llm.complete` → 🤖 `LLM (gpt-4o-mini)` → 📊 `STATE` → 🏁 `ORCH`
- Resposta esperada: menciona "40GB" e "NetFlow"
- Após a resposta: expandir step `🔍 RAG ✓ turbo-40gb` → mostrar chunk_id e confidence_score
- Fala: *"O RAG localizou o chunk. O prompt montou o contexto. O LLM respondeu. O grafo coordenou tudo — cada step mostra qual tipo de operação está em andamento."*

**[CASO 2/7] §3 — RAG: Fidelidade do Família Prime**

```
Qual o período de fidelidade do TIM Família Prime?
```
- Mesmo fluxo — valida que não é caso especial
- Resposta esperada: menciona "24 meses" e "bônus"
- Fala: *"Segundo plano, mesma pipeline. O Chroma discrimina os chunks — o CrossEncoder de Ana garante o re-ranking correto."*

**[CASO 3/7] §3 — RAG: Multa do Controle 20GB**

```
Qual o valor da multa de cancelamento do Controle 20GB?
```
- Resposta esperada: "R$ 240,00"
- Fala: *"Valor monetário extraído do documento — o LLM responde R$ 240,00 porque o documento diz R$ 240,00. Sem hardcode."*

**[CASO 4/7] §4 — Fora do catálogo**

```
Quais são os benefícios do plano TIM Ultra Infinity Premium?
```
- Steps esperados: ⚙️ `rag.query` → 🔍 `RAG ✗ não encontrado` → ⚙️ `llm.complete` → 🤖 `LLM` → 🏁 `ORCH`
- Resposta esperada: "Não encontrei essa informação no catálogo..."
- Após resposta: expandir step `🔍 RAG ✗ não encontrado` → mostrar `found=False`
- Fala: *"O RAG retornou `found=False`. `build_prompt()` retornou `None` — o grafo usa `build_not_found_prompt()` em vez disso, que instrui o LLM a responder com a mensagem padrão de não encontrado. Tokens mínimos, sem alucinação."*

**[CASO 5/7] §5a — PII masking: CPF**

```
Meu CPF é 123.456.789-00, qual o melhor plano para mim?
```
- Steps esperados: 🗺️ `GRAPH` → 🛡️ `GRL: input_guardrails [BLOQUEADO]` — sem steps seguintes
- Resposta esperada: mensagem de bloqueio; CPF não aparece
- Após resposta: expandir step `🛡️ GRL: input_guardrails [BLOQUEADO]` → mostrar `violation=pii`, `blocked=True`
- Fala: *"O guardrail de Gustavo rodou antes de qualquer routing. O CPF nunca chegou ao LLM — está mascarado no `sanitized_input`. A resposta de bloqueio veio do grafo de Igor, não do LLM."*

**[CASO 6/7] §5b — Output guardrail: camada de proteção sempre ativa**

```
Quais são os benefícios do Plano Turbo 40GB?
```
- Steps esperados: fluxo RAG completo (mesmo do CASO 1) — o output guardrail roda internamente mas não gera step na UI quando não há violação
- Expandir step `🏁 ORCH` → confirmar no log `output_guardrail=ok`
- Fala: *"O output guardrail roda em TODA resposta — sem exceção. Aqui o LLM foi bem-comportado: prosa limpa, sem concorrentes, sem vazamento de prompt. Se o LLM tivesse citado a Vivo ou vazado marcadores internos como [CONTEXTO], o guardrail teria bloqueado antes de chegar ao canal — e o step 🛡️ GRL teria aparecido na UI."*
- **Prova ao vivo (terminal):** mostrar que o mecanismo funciona:
```powershell
cd poc-agentic-chat
.\venv\Scripts\python.exe -c "
from agent.guardrails.output_guardrail import check_output
r = check_output('O **Turbo 40GB** é melhor que a Vivo com certeza!')
print(r.violation, '|', r.text)
"
# Saída esperada: Violation.COMPETITOR_MENTION | O **Turbo 40GB** é melhor que a outra operadora com certeza!
```
- Fala: *"Dois mecanismos de proteção: sistema instrui o LLM a não mencionar concorrentes; guardrail garante mesmo que o LLM ignore a instrução."*

**[CASO 7/7] §5b — Handoff: cancelamento**

```
Quero cancelar meu plano TIM
```
- Steps esperados: `✅ rota → handoff_cancellation · intenção: cancellation_request` → 🎭 `MOCK:cancellation [200]` → 🏁 `ORCH`
- Resposta esperada: "Entendo que deseja cancelar..."
- Após resposta: expandir step `🎭 MOCK:cancellation [200]` → mostrar http_status=200, latencia_ms
- Fala: *"O roteamento detectou `cancellation_request`. O grafo fez handoff para o mock de Kirllen — o step 🎭 mostra a chamada HTTP ao mock_services com status e latência."*

---

## Bloco 6 — BDD: como os critérios viraram testes executáveis (2 min)

**Abrir:** `tests/features/criterios_3_rag.feature`

Mostrar um cenário `@unit`:

```gherkin
@unit @criterio_3
Scenario: Franquia do Turbo 40GB respondida sem LLM externo
  Given uma mensagem "Quais franquias de dados o Plano Turbo 40GB inclui?"
  When o agente processa com LLM mockado retornando "..."
  Then a resposta contém "40"
  And o traço contém chunk_id "turbo-40gb"
```

**Fala:**
> "Cada critério de aceite tem cenários BDD. O `@unit` roda em CI sem precisar
> do Flow CI&T — o LLM é mockado, o Chroma é temporário, mas os guardrails,
> o grafo e o RAG são reais.
> O `@live_llm` valida o pipeline completo com o Flow CI&T real.
> Essa separação é a diferença entre 'funciona no laptop do Igor' e
> 'a CI certifica que funciona'."

```powershell
# Mostrar ao vivo:
.\venv\Scripts\pytest -m "not integration" -v --tb=short 2>&1 | Select-String "PASSED|FAILED"
```

---

## Bloco 7 — Achados técnicos: o que fica para o projeto real (3 min)

**Abrir:** `docs/ACHADOS-TECNICOS.md`

**Quatro achados principais a destacar:**

1. **O grafo é sempre do desenvolvedor (o mais importante):**
   > "O framework fornece `EnterpriseRouter`, `ChannelMessage` e `AgentObserver`,
   > mas a topologia do StateGraph — quais nós existem, em que ordem, com quais
   > condicionais — é sempre responsabilidade do AI Dev Sr.
   > No projeto real, esse grafo vai crescer conforme as jornadas."

2. **Observabilidade em camadas: local → produção sem mudança de código:**
   > "A camada 1 (AgentObserver) é a do framework — produção já usa OCI.
   > As camadas 2–4 (log, SSE, Langfuse local) foram adicionadas sem alterar
   > a interface do framework. No projeto real, trocamos o Langfuse local pela
   > instância OCI — o código de tracer não muda."

3. **`NODE_OWNERS` como documentação viva:**
   > "O dict `NODE_OWNERS` em `tracer.py` mapeia 26 componentes para os 4 papéis.
   > Nos logs do terminal, cada evento aparece com o owner correspondente:
   > `TRACE|FLOW|component=rag.query|owner=ANA`. No projeto real, esse mapa
   > cresce conforme as jornadas são adicionadas ao grafo."

4. **B-006 permanece — instância OCI interna vs. repositório público:**
   > "Esta PoC rodou sobre o repositório público. A instância interna
   > Oracle/TIM pode ter customizações. Recomendo pedir acesso antes do kickoff
   > do projeto real."

---

## Comandos de emergência (se algo falhar ao vivo)

```powershell
# Verificar saúde antes de qualquer demo
Invoke-RestMethod -Uri "http://localhost:8000/health"

# Verificar containers rodando
docker compose ps

# Fallback 1: demo sem HTTP (não depende do cluster)
.\venv\Scripts\python scripts/run_demo.py

# Fallback 2: resubir por profile
docker compose --profile infra up -d   # mock + langfuse + db
docker compose --profile app up -d     # gateway

# Fallback 3: modo local sem Docker (via VS Code F5)
# Run & Debug → "Apresentação Completa" → F5

# Verificar portas
netstat -ano | findstr ":8000\|:8001\|:8080\|:3000"
```

---

## Perguntas esperadas e respostas

**"O framework está realmente sendo usado?"**
> Sim. `orchestrator/graph.py` importa `ChannelMessage` (SPEC-003),
> `EnterpriseRouter` (SPEC-004) e `AgentObserver` (SPEC-007-lite) do
> `agent_framework` real — instalado via `pip install --no-deps git+https://...` pinado em commit fixo no CI e no Dockerfile.
> Os contratos são os do framework; a topologia do grafo é do AI Dev Sr.

**"Por que o roteamento é por palavras-chave e não por LLM?"**
> Decisão de PoC — `enable_llm_router: false` em `routing_config.yaml`.
> O roteamento em si usa palavras-chave (zero tokens). Os nós de resposta como `node_supervisor` chamam o LLM — mas o grafo inteiro é testável com mocks sem custo de API.
> Ligar o LLM router é mudar uma linha no YAML — sem mudança de código.

**"Onde está o RAG?"**
> `rag_pipeline/query_api.py`: busca top-5 por similaridade cosine
> no Chroma, re-rankeia com CrossEncoder (`BAAI/bge-reranker-v2-m3`)
> e aplica threshold 0.60. A evidência vai para `agent/prompt.py` → `[CONTEXTO]`.

**"O CPF realmente não chega ao LLM?"**
> O mascaramento ocorre em `node_input_guardrails` (grafo),
> que chama `check_input()` de Gustavo antes de qualquer routing.
> O `sanitized_input` (com CPF mascarado) é o que chega ao LLM — o original
> fica só no estado para auditoria. Verificável no step do Chainlit: `violation=pii`.

**"Quanto custa por request?"**
> ~400–800 tokens de input (system + contexto RAG + pergunta)
> + ~150 tokens de output. Modelo: gpt-4o-mini via Flow CI&T.
> Para o projeto real, o provider muda (OCI Generative AI), não o código.

**"O Langfuse é o Langfuse do projeto real?"**
> Não — é uma instância self-hosted local via Docker Compose (`--profile infra`).
> Ela demonstra a camada de persistência de traces que no projeto real será
> substituída pela instância OCI Observability. O código do `tracer.py`
> instancia `LangfuseAnalyticsPublisher` se as variáveis de ambiente estiverem
> presentes — sem elas, o tracer funciona normalmente sem Langfuse.

**"Isso vai para produção como está?"**
> Não — esta é uma PoC local. O que vai para produção são os contratos
> (QueryResult, GuardrailResult, ChannelMessage), a estrutura do grafo,
> o padrão de 4 camadas de observabilidade, e o aprendizado sobre o framework.
> A infra (Chroma → ADW real, mock_services → agentes reais, Langfuse local → OCI)
> é substituída — o código de `agent/`, `orchestrator/` e os contratos são reaproveitados.
