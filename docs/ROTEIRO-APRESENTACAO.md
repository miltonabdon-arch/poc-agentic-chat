# Roteiro de Apresentação — Agente de Catálogo TIM (PoC)
**Data:** 2026-08-18 | **Apresentador:** Igor Scaglia (AI Developer Sr, CI&T)
**Duração estimada:** 20–25 minutos

---

## Objetivo da apresentação

Mostrar que o framework `agent_platform_oci` é viável como base do Agente de
Planos e Ofertas — rodando ponta a ponta em ambiente local, com LLM real (Flow CI&T).

Resultado esperado: o time sai com confiança técnica para adotar o framework
no projeto real.

---

## Estrutura (com timing)

| # | Bloco | Arquivo(s) a mostrar | Tempo |
|---|-------|----------------------|-------|
| 1 | Contexto: o que é a PoC e por que ela existe | `docs/PROPOSTA-POC.md` | 2 min |
| 2 | Arquitetura: o grafo LangGraph e os 11 nós | `orchestrator/graph.py` L42–231 | 4 min |
| 3 | Responsabilidades do time (quem fez o quê) | `orchestrator/graph.py` + módulos | 3 min |
| 4 | **DEMO AO VIVO** — 5 casos via HTTP | `scripts/test_http.ps1` | 7 min |
| 5 | Por dentro da demo (mostrar código enquanto responde) | `agent/guardrails/`, `agent/prompt.py` | 4 min |
| 6 | O que fica para o projeto real | `STATE.md` → Deferred Ideas | 2 min |
| 7 | Perguntas | — | livre |

---

## Bloco 1 — Contexto (2 min)

Abrir `docs/PROPOSTA-POC.md` e mostrar apenas:
- **Objetivo:** validar `agent_platform_oci` em 2 semanas
- **Escopo deliberadamente limitado:** catálogo local, LLM mock → LLM real, sem infraestrutura de nuvem
- "O que fazemos aqui é exatamente o que vai para produção — mesmos contratos, mesmo framework"

**Fala sugerida:**
> "Esta PoC não é código descartável. Ela valida os contratos de dados,
> o grafo de estados e o roteamento do framework que vamos usar no projeto real.
> O que está aqui em `ChannelMessage`, `QueryResult` e `GuardrailResult`
> vai direto para o Agente POV — sem reescrita."

---

## Bloco 2 — Arquitetura: o grafo LangGraph (4 min)

### Abrir: `orchestrator/graph.py`

**L42–50** — mostrar `GraphState` (TypedDict):
```python
class GraphState(TypedDict):
    channel_message: ChannelMessage   # contrato do agent_framework
    sanitized_input: str              # saída do guardrail de input
    route: str                        # decisão do EnterpriseRouter
    ...
```
> "O estado flui pelo grafo. Cada nó recebe e devolve GraphState — é o
> padrão do LangGraph, o mesmo que o `agent_platform_oci` usa internamente."

**L188–231** — mostrar `build_graph()`:
- Apontar os 11 nós no `add_node`
- Mostrar as 2 arestas condicionais: `_after_guardrails` (L166) e `_after_routing` (L170)
- Mostrar `g.set_entry_point("input_guardrails")` — é sempre o primeiro nó

**Diagrama verbal do fluxo:**
```
POST /agent/interact
  → channel_gateway.normalize()  → ChannelMessage
  → input_guardrails             → [BLOCK se PII out-of-domain]
  → routing_decision             → EnterpriseRouter lê routing_config.yaml
  → catalog_agent | billing | handoff_cancellation | handoff_deals | ...
  → output_guardrails            → [MASK concorrente | BLOCK context-leak]
  → judge                        → log offline
  → resposta
```

**Breakpoint sugerido:** L234 — `_compiled_graph = build_graph().compile()`
> "Aqui o grafo é compilado no startup da aplicação. Em tempo de request,
> chamamos `ainvoke` — não há compilação no caminho crítico."

---

## Bloco 3 — Responsabilidades do time (3 min)

Mostrar os módulos e quem implementou cada um:

| Módulo | Responsável | O que valida do framework |
|--------|-------------|--------------------------|
| `rag_pipeline/vectorizer.py` | Ana (Data Engineer) | Chroma como ADW local |
| `rag_pipeline/query_api.py` | Ana | CrossEncoder re-ranking |
| `agent/judge.py` | Gustavo (AI Scientist) | Checagem offline de alucinação |
| `agent/guardrails/` | Gustavo | PII masking + filtro de concorrentes |
| `agent/prompt.py` | Gustavo | Montagem estruturada do contexto RAG |
| `gateway/app.py` | Kirllen (Backend) | Runtime FastAPI + Channel Gateway |
| `orchestrator/graph.py` | Igor (AI Dev Sr) | Grafo LangGraph + EnterpriseRouter |

> "Cada fatia foi desenvolvida por um papel diferente, sem depender das
> outras no meio do sprint. Os contratos (`QueryResult`, `GuardrailResult`,
> `Interaction`) são a cola — e funcionaram."

---

## Bloco 4 — DEMO AO VIVO (7 min)

**Pré-requisito:** cluster rodando via VS Code `Cluster Local (app + mock-services)` F5.

### Comando a executar:
```powershell
cd c:\projects\ciandt\tim\src\poc-agentic-chat
.\scripts\test_http.ps1
```

### Casos e o que mostrar em cada um:

**[1/5] Catálogo RAG — Turbo 40GB**
> Pergunta: "Quais franquias de dados o Plano Turbo 40GB inclui?"
- Esperado: resposta com "40GB de internet 4G/5G e 10GB adicionais via NetFlow"
- Ponto de destaque: **"O LLM respondeu só com o que estava no Chroma. Sem invenção."**

**[2/5] Catálogo RAG — Família Prime (fidelidade)**
> Pergunta: "Existe fidelidade no Plano Família Prime?"
- Esperado: "fidelidade de 24 meses... bônus de 10GB adicionais"
- Ponto de destaque: **"Segundo plano, mesma pipeline RAG → sem hardcode"**

**[3/5] Fora do catálogo**
> Pergunta: "Qual o preço do Plano Estratosférico 500GB?"
- Esperado: `not_found_response()` — "Não encontrei essa informação..."
- Ponto de destaque: **"Plano inexistente. O sistema não inventa. É a regra mais importante."**
- Mostrar código: `agent/prompt.py` L126–127:
  ```python
  if not query_result.found:
      return None   # orquestrador chama not_found_response()
  ```

**[4/5] Handoff — Cancelamento**
> Pergunta: "Quero cancelar minha linha"
- Esperado: "[Agente Retenção] Entendo que deseja cancelar..."
- Ponto de destaque: **"O grafo detectou a intenção, fez handoff para o mock do Agente de Retenção. No projeto real, é uma chamada real para o agente de cancelamento."**
- Mostrar código: `orchestrator/routing_config.yaml` L51–62 (intenção `cancellation_request`)

**[5/5] PII masking**
> Pergunta: "Meu CPF é 123.456.789-00, qual meu plano atual?"
- Esperado: CPF nunca chega ao LLM — `not_found_response()`
- Ponto de destaque: **"O CPF foi mascarado antes de qualquer chamada ao LLM. Nem o log vê o dado real."**
- Mostrar código: `agent/guardrails/input_guardrail.py` L57–75 (mascaramento em cadeia)

---

## Bloco 5 — Por dentro da demo (4 min)

### Guardrail de input — `agent/guardrails/input_guardrail.py`

**L36–48** — padrões de PII:
```python
_CPF_RE  = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_CNPJ_RE = ...
_EMAIL_RE = ...
_PHONE_RE = ...   # DDD obrigatório para reduzir falsos positivos
```
> "Regex calibrada para reduzir falsos positivos — exige DDD no telefone,
> CNPJ antes de CPF para evitar ambiguidade."

**L57–75** — `check_input()`: ordem out-of-domain → PII masking.

### Prompt builder — `agent/prompt.py`

**L64–75** — `_SYSTEM_PROMPT`: identidade + regras fixas (role:system)
> "Separamos system/user — é o pré-requisito para tool-calling real via MCP no projeto real."

**L126–127** — retorna `None` quando `found=False`:
> "O LLM nunca é chamado para planos que não existem. Sem alucinação por design."

**L137–146** — seção `[CONTEXTO]` com `source_document_id`:
> "O ID da fonte vai para o judge offline — ele verifica se a resposta
> está ancorada em uma evidência real."

### Judge offline — `agent/judge.py` L37–54

> "Três checks: groundedness, not-found consistency e length anomaly.
> Não bloqueia o fluxo síncrono — roda sobre o lote depois."

---

## Bloco 6 — O que fica para o projeto real (2 min)

Abrir `STATE.md` → seção "Deferred Ideas":

1. **State Store compartilhado (Redis/AlloyDB):** aqui o estado é in-memory por request. No projeto real, precisa persistir entre turnos e agentes.
2. **Judge com Golden Standard Dataset:** aqui fazemos 3 checks por proxy. O projeto real precisa de um dataset de avaliação curado.
3. **LLM Router ativo (`enable_llm_router: true`):** aqui o roteamento é por palavras-chave (YAML). No projeto real, o LLM classifica a intenção.
4. **Integração OCI real:** aqui o `agent_framework` é vendorizado localmente. No projeto, vem do repositório privado da TIM/Oracle.

> "Esses 4 pontos são a lista de trabalho do projeto real — não são dívidas técnicas desta PoC, são extensões deliberadamente postergadas para manter o foco nas 2 semanas."

---

## Comandos de emergência (se algo falhar ao vivo)

```powershell
# Fallback 1: demo sem HTTP (não depende do cluster)
cd c:\projects\ciandt\tim\src\poc-agentic-chat
python scripts/run_demo.py

# Fallback 2: resubir cluster manualmente
# Terminal 1:
cd mock_services; uvicorn app:app --host 0.0.0.0 --port 8001
# Terminal 2:
$env:PYTHONPATH="."; foreach($l in Get-Content .env){if($l -match "^([^#=][^=]*)=(.*)$"){[System.Environment]::SetEnvironmentVariable($Matches[1].Trim(),$Matches[2].Trim())}}
uvicorn gateway.app:app --host 0.0.0.0 --port 8000

# Verificar portas ativas
netstat -ano | findstr ":8000\|:8001"
```

---

## Perguntas esperadas e respostas

**"O framework está realmente sendo usado?"**
> Sim. `orchestrator/graph.py` L19–20 importa `ChannelMessage` e `EnterpriseRouter`
> do `agent_framework` real (vendorizado de `agent_platform_oci/libs/agent_framework`).
> `gateway/app.py` usa `AgentObserver`. Os contratos são os do framework.

**"Por que o roteamento é por palavras-chave e não por LLM?"**
> Decisão deliberada de PoC — `enable_llm_router: false` em `routing_config.yaml`.
> Mantém o roteamento determinístico e sem custo de tokens para validar a
> estrutura do grafo. Ligar o LLM router é mudar uma linha no YAML.

**"Onde está o RAG?"**
> `rag_pipeline/query_api.py` — busca top-5 por similaridade cosine no Chroma,
> re-rankeia com `BAAI/bge-reranker-v2-m3` (CrossEncoder) e aplica threshold.
> A evidência vai para `agent/prompt.py` → seção `[CONTEXTO]`.

**"Qual o custo de tokens por request?"**
> Depende do tamanho do chunk RAG retornado. Estimativa: 400–800 tokens
> de input (system + contexto RAG + pergunta) + ~150 tokens de output.
> Modelo: gpt-4o-mini via Flow CI&T.

**"Isso vai para produção como está?"**
> Não — esta é uma PoC local. O que vai para produção são os contratos,
> a estrutura do grafo e o aprendizado sobre o framework.
> A infra (Chroma → ADW real, uvicorn local → OCI, mock_services → agentes reais)
> é substituída, mas o código de `agent/`, `orchestrator/` e os contratos de dados são reaproveitados.
