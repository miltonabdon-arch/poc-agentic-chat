# Roteiro de Apresentação — Agente de Catálogo TIM (PoC)

**Data:** 2026-08-18 | **Apresentador:** Igor Scaglia (AI Developer Sr, CI&T)
**Duração estimada:** 25–30 minutos

---

## Fio condutor da apresentação

A narrativa percorre o arco completo de uma PoC colaborativa:

> **Hipótese** (PROPOSTA-POC §3) →
> **Contratos definidos** (kickoff) →
> **Cada papel entrega sua fatia** (paralelo) →
> **Conflitos encontrados e resolvidos** (integração) →
> **Grafo montado** (AI Dev Sr) →
> **Demo contra os critérios** →
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
| 4 | O que eu recebi e o que faltava: montar o grafo | 3 min |
| 5 | **DEMO AO VIVO** — 7 casos vs. os critérios de aceite | 8 min |
| 6 | BDD: como os critérios viraram testes executáveis | 2 min |
| 7 | Achados técnicos: o que ficou para o projeto real | 3 min |
| 8 | Perguntas | livre |

---

## Preparação (antes de entrar na sala)

Executar nesta ordem — não durante a apresentação.

**1. Ingestão** (só se `chroma_data/` não existir ou estiver vazio)

VS Code → Run & Debug → **"Ingestão (run_ingestao.py)"** → F5.
Aguardar: `Ingestão concluída: 8 documentos, 32 chunks`.

**2. Subir o cluster** (caminho primário — VS Code)

VS Code → Run & Debug → **"Cluster Local (app + mock-services)"** → F5.
Aguardar `Application startup complete.` nos dois terminais integrados.

> Alternativa (se VS Code indisponível): `docker compose up -d` via WSL.

**3. Verificar saúde**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
# Retorno esperado: {"status":"ok"}
```

**4. Smoke test** (confirmar RAG antes de entrar na sala)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/agent/interact" `
  -Method POST -ContentType "application/json" `
  -Body '{"message": "Quais franquias de dados o Plano Turbo 40GB inclui?"}'
# Deve retornar resposta mencionando "40GB" — não a mensagem de fallback
```

Se o smoke test falhar: verificar logs no terminal integrado do VS Code antes de entrar na sala.

> **Atenção — warm-up do modelo:** a primeira requisição após subir o cluster
> demora 30–60s porque o `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`)
> e o CrossEncoder (`BAAI/bge-reranker-v2-m3`) carregam os pesos em memória na
> primeira chamada. As chamadas seguintes são imediatas — o modelo fica em memória
> enquanto o processo estiver de pé. **O smoke test (passo 4 acima) serve exatamente
> para absorver esse warm-up antes de entrar na sala.** Nunca faça a primeira
> requisição ao vivo na frente da audiência.

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
- O que veio pronto: `build_prompt(question, query_result)`, `not_found_response()`, `check_input(text)`, `check_output(text)`
- Ponto crítico: `build_prompt()` retorna `None` quando `found=False` — isso obrigou o grafo a nunca chamar o LLM para planos inexistentes

**Mostrar (30 segundos):** `agent/prompt.py` L126–127 — o `if not query_result.found: return None`.

### Kirllen (Backend/Integração) — gateway/ + mock_services/

- Branch: `backend` (entregue via PR #1)
- Entregáveis: `channel_gateway.py`, `app.py`, `mock_services/` completo (CRM, cancellation, deals, plans)
- O que veio pronto: `normalize(raw_message) → ChannelMessage` e o runtime FastAPI
- Valor do mock_services: os handoffs de cancelamento e deals funcionam localmente sem nenhuma integração real

**Mostrar (30 segundos):** `gateway/channel_gateway.py` L11–19 — a função `normalize()` que cria o `ChannelMessage`.

---

## Bloco 4 — O que eu recebi e o que faltava: montar o grafo (3 min)

**Fala sugerida:**
> "Eu recebi três branches, três contratos implementados, e o `agent_framework`
> com `ChannelMessage`, `EnterpriseRouter` e `AgentObserver`.
> O framework não monta o grafo — essa é a responsabilidade explícita do AI Dev Sr.
> Foi o principal aprendizado prático desta PoC."

**Mostrar:** `orchestrator/graph.py` L1–12 — o docstring com a tabela de atribuição:

```
Ana Carolina → QueryResult      (rag_pipeline/query_api.py)
Gustavo      → GuardrailResult  (agent/guardrails/, branch test_new_branch)
Kirllen      → ChannelMessage   (gateway/channel_gateway.py, branch backend)
Igor         → build_graph(), run_interaction()
```

**Mostrar:** `orchestrator/graph.py` L191–231 — `build_graph()`:
- `g.add_node("input_guardrails", node_input_guardrails)` — código do Gustavo, nó do grafo de Igor
- `g.add_conditional_edges("input_guardrails", _after_guardrails)` — a lógica block/allow
- `g.set_entry_point("input_guardrails")` — sempre começa pelo guardrail, nunca pelo agente

**Mostrar:** `orchestrator/graph.py` L272–316 — `_run_catalog()`:
> "Aqui o grafo integra as três fatias: QueryResult de Ana, build_prompt de Gustavo,
> complete() via Flow CI&T. Cada contrato chegou de uma branch diferente;
> este nó é onde eles se encontram."

**Conflito que precisou resolver (AD-008 → AD-009 → AD-010):**
> "A primeira tentativa de integrar o `agent_framework` causou conflitos
> com as outras branches em andamento. Revertemos, esperamos as branches
> ficarem prontas, e reintroduzimos via vendoring — 3 dias de custo,
> aprendizado real para o projeto."

---

## Bloco 5 — DEMO AO VIVO (8 min)

**Pré-requisito:** cluster rodando.

```powershell
# Verificar saúde antes de rodar qualquer demo
Invoke-RestMethod -Uri "http://localhost:8000/health"
# Deve retornar: {"status":"ok","chroma":"ok"}
```

### Executar:
```powershell
cd c:\projects\ciandt\tim\src\poc-agentic-chat
.\scripts\test_http.ps1
```

### Casos e narrativa de cada um:

**[CASO 1/7] §3 — RAG: Franquia do Turbo 40GB**
> "Pergunta real, plano real no catálogo."
- Resultado esperado: "40GB de internet 4G/5G e 10GB adicionais via NetFlow"
- Narrativa: "O RAG localizou o chunk em Ana, o prompt de Gustavo montou o contexto, o LLM do Flow CI&T respondeu. Sem hardcode."
- Trace a mostrar no log: `chunk_id=turbo-40gb#Franquia`

**[CASO 2/7] §3 — RAG: Fidelidade do Família Prime**
> "Segundo plano, mesma pipeline — valida que não é um caso especial."
- Resultado esperado: "fidelidade de 24 meses... bônus de 10GB"
- Trace: `chunk_id=familia-prime#Fidelidade`

**[CASO 3/7] §3 — RAG: Multa do Controle 20GB**
> "Terceiro tipo de dado — valor monetário. O LLM responde com R$240,00 porque o documento diz R$240,00."
- Resultado esperado: "R$ 240,00"
- Trace: `chunk_id=controle-20gb#Multa de cancelamento`

**[CASO 4/7] §4 — Fora do catálogo**
> "Plano que não existe."
- Resultado esperado: `"Não encontrei essa informação no catálogo..."`
- Narrativa: "O RAG retornou `found=False`. O grafo nunca chamou o LLM.
  `build_prompt()` de Gustavo retornou `None` — é a regra mais importante da PoC."
- Trace: `chunk_id=nenhum`

**[CASO 5/7] §5a — PII masking: CPF**
> "Mensagem com CPF de teste."
- Resultado esperado: CPF não aparece na resposta nem no log
- Narrativa: "O guardrail de input de Gustavo rodou antes de qualquer chamada ao LLM.
  O dado sensível nunca chegou ao modelo."
- Trace: `guardrails_acionados=['input:pii']`

**[CASO 6/7] §5b — Output guardrail: concorrente**
> "Pergunta que tenta forçar comparação com concorrente."
- Resultado esperado: "outra operadora" onde estaria "OperadoraZ"
- Narrativa: "O LLM pode mencionar um concorrente na saída — o guardrail de output
  mascara antes de devolver ao canal."

**[CASO 7/7] §5b — Handoff: cancelamento**
> "Intenção clara de cancelar."
- Resultado esperado: "[Agente Retenção] Entendo que deseja cancelar..."
- Narrativa: "O EnterpriseRouter do framework detectou a intenção `cancellation_request`.
  O grafo fez handoff para o mock do Agente de Retenção de Kirllen."

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
.\venv\Scripts\pytest -m unit -v --tb=short 2>&1 | Select-String "PASSED|FAILED"
```

---

## Bloco 7 — Achados técnicos: o que fica para o projeto real (3 min)

**Abrir:** `docs/ACHADOS-TECNICOS.md`

**Três achados principais a destacar:**

1. **O grafo é sempre do desenvolvedor (o mais importante):**
   > "O framework fornece `EnterpriseRouter`, `ChannelMessage` e `AgentObserver`,
   > mas a topologia do StateGraph — quais nós existem, em que ordem, com quais
   > condicionais — é sempre responsabilidade do AI Dev Sr.
   > No projeto real, esse grafo vai crescer conforme as jornadas."

2. **`AgentObserver` noop precisou de segunda camada:**
   > "Localmente, o `AgentObserver` não imprime nada — ele espera um
   > `analytics` real (Langfuse, OCI). Adicionamos uma segunda camada de
   > logging (`TRACE|tipo|campo=valor`). No projeto real, é a instância OCI
   > que resolve isso."

3. **B-006 permanece — instância OCI interna vs. repositório público:**
   > "Esta PoC rodou sobre o repositório público. A instância interna
   > Oracle/TIM pode ter customizações. Recomendo pedir acesso antes do kickoff
   > do projeto real."

---

## Comandos de emergência (se algo falhar ao vivo)

```powershell
# Verificar saúde antes de qualquer demo
Invoke-RestMethod -Uri "http://localhost:8000/health"

# Fallback 1: demo sem HTTP (não depende do cluster)
.\venv\Scripts\python scripts/run_demo.py

# Fallback 2: resubir cluster manualmente
# Terminal 1 — mock services:
.\venv\Scripts\uvicorn mock_services.app:app --port 8001

# Terminal 2 — gateway (carregar .env primeiro):
foreach($l in Get-Content .env){if($l -match "^([^#=][^=]*)=(.*)$"){[System.Environment]::SetEnvironmentVariable($Matches[1].Trim(),$Matches[2].Trim())}}
$env:PYTHONPATH = "."
.\venv\Scripts\uvicorn gateway.app:app --port 8000

# Verificar portas
netstat -ano | findstr ":8000\|:8001"
```

---

## Perguntas esperadas e respostas

**"O framework está realmente sendo usado?"**
> Sim. `orchestrator/graph.py` L1–12 importa `ChannelMessage` (SPEC-003),
> `EnterpriseRouter` (SPEC-004) e `AgentObserver` (SPEC-007-lite) do
> `agent_framework` real — vendorizado de `agent_platform_oci/libs/`.
> Os contratos são os do framework; a topologia do grafo é do AI Dev Sr.

**"Por que o roteamento é por palavras-chave e não por LLM?"**
> Decisão de PoC — `enable_llm_router: false` em `routing_config.yaml`.
> Mantém determinismo e custo zero de tokens para validar a estrutura do grafo.
> Ligar o LLM router é mudar uma linha no YAML — sem mudança de código.

**"Onde está o RAG?"**
> `rag_pipeline/query_api.py` L55–89: busca top-5 por similaridade cosine
> no Chroma, re-rankeia com CrossEncoder (`BAAI/bge-reranker-v2-m3`)
> e aplica threshold 0.7. A evidência vai para `agent/prompt.py` → `[CONTEXTO]`.

**"O CPF realmente não chega ao LLM?"**
> O mascaramento ocorre em `node_input_guardrails` (grafo),
> que chama `check_input()` de Gustavo antes de qualquer routing.
> O `sanitized_input` (com CPF mascarado) é o que chega ao LLM — o original
> fica só no estado para auditoria. Verificável no trace: `violation=pii`.

**"Quanto custa por request?"**
> ~400–800 tokens de input (system + contexto RAG + pergunta)
> + ~150 tokens de output. Modelo: gpt-4o-mini via Flow CI&T.
> Para o projeto real, o provider muda (OCI Generative AI), não o código.

**"Isso vai para produção como está?"**
> Não — esta é uma PoC local. O que vai para produção são os contratos
> (QueryResult, GuardrailResult, ChannelMessage), a estrutura do grafo
> e o aprendizado sobre o framework.
> A infra (Chroma → ADW real, mock_services → agentes reais, vendoring → PyPI interno)
> é substituída — o código de `agent/`, `orchestrator/` e os contratos são reaproveitados.
