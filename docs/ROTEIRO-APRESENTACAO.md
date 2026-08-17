# Roteiro de Apresentação — AI Developer Sr
## PoC Agente de Catálogo TIM | 17/08/2026

**Duração:** 20 minutos  
**Ambiente:** VS Code + Cluster Local (app:8000 + mock-services:8001)  
**Branch:** `feature/orchestrator-agentframework-native`

---

## [0–3 min] Contexto — Slides 1–3

**Fala:**
> "Sou o AI Dev Sr. Minha responsabilidade foi a camada de orquestração —
> a cola que une todos os módulos do time usando os contratos nativos do
> `agent_framework`. O objetivo da PoC é validar que o framework é viável
> como base do Agente de Planos e Ofertas real."

**Slide 1:** Proposta da PoC  
**Slide 2:** Arquitetura e divisão de papéis  
**Slide 3:** O que o AI Dev Sr entregou

---

## [3–8 min] Código — O que foi implementado

Abrir VS Code. Mostrar os arquivos na ordem abaixo.

### `orchestrator/graph.py`
- Mostrar `class GraphState` (linha ~41) — o envelope que passa entre os nós
- Mostrar `build_graph()` (linha ~187) — os 11 nós registrados
- Mostrar `node_routing_decision` (linha ~75) — `EnterpriseRouter` nativo do framework
- Mostrar `run_interaction()` (linha ~240) — entrypoint público, async

**Fala:**
> "O grafo LangGraph é o principal entregável. Cada nó é uma função async
> com responsabilidade única. O roteamento usa o `EnterpriseRouter` real do
> `agent_framework` — não é um if/else manual."

### `orchestrator/routing_config.yaml`
- Mostrar a estrutura de intents + keywords + agent
- **Destacar:** "Para adicionar um novo agente, só edita este YAML."

### `gateway/channel_gateway.py`
- Mostrar que retorna `ChannelMessage` (contrato nativo do framework)

### O que está **fora de escopo** (dizer explicitamente):
> "State store compartilhado entre agentes (Redis/AlloyDB) e o grafo com
> memória persistida são deferred para o projeto real — registrados no
> STATE.md como decisão consciente, não como dívida técnica."

---

## [8–14 min] Demo ao Vivo — Terminal do VS Code

Abrir terminal integrado (Ctrl+`). Rodar na ordem:

### 1. RAG + LLM — o coração da PoC
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/agent/interact `
  -ContentType "application/json" `
  -Body '{"message": "Quais franquias de dados o Plano Turbo 40GB inclui?"}'
```
**Mostrar:** `response` com os dados reais do catálogo vindos do Chroma.

### 2. PII Masking — guardrail de entrada
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/agent/interact `
  -ContentType "application/json" `
  -Body '{"message": "Meu CPF é 123.456.789-00, qual meu plano?"}'
```
**Mostrar:** CPF não aparece na resposta — foi mascarado pelo `input_guardrail`
antes de chegar ao LLM.

### 3. Cancelamento — handoff para mock-services
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/agent/interact `
  -ContentType "application/json" `
  -Body '{"message": "Quero cancelar minha linha."}'
```
**Mostrar:** resposta de handoff — o orquestrador encaminhou para o agente
de cancelamento via `mock-services:8001`.

---

## [14–18 min] Demo "Novo Agente" — skill `/novo-agente`

**Fala:**
> "O framework estrutura a criação de qualquer novo agente em 4 passos.
> Vou mostrar como adicionaríamos um Agente de Reclamações."

No Claude Code, chamar: `/novo-agente`

Responder as perguntas de design ao vivo. Claude gera:
- `agent/reclamacao_agent.py`
- Entrada no `routing_config.yaml`
- Registro do nó em `graph.py`

**Fala:**
> "Isso é o que diferencia o framework de um protótipo: qualquer desenvolvedor
> do time segue o mesmo contrato, sem alucinação de arquitetura."

---

## [18–20 min] Conclusão + Perguntas — Slide 10

**Fala:**
> "Viabilidade confirmada. O `agent_framework` rodou ponta a ponta com o LLM
> real (Flow CI&T / gpt-4o-mini). RAG funcionando, guardrails ativos, roteamento
> por intenção via YAML, tracing com `AgentObserver`. Próximo passo: integrar
> no repositório principal do projeto."

---

## Breakpoints sugeridos (VS Code)

| Arquivo | Linha aprox. | Quando ativar | O que mostra |
|---|---|---|---|
| `orchestrator/graph.py` | `node_input_guardrails` | Demo PII | Texto sendo sanitizado antes do LLM |
| `orchestrator/graph.py` | `node_routing_decision` | Qualquer chamada | `EnterpriseRouter` retornando o agente escolhido |
| `orchestrator/graph.py` | `_run_catalog` | Demo RAG | `query()` + `build_prompt()` + `complete()` |
| `orchestrator/graph.py` | `node_judge` | Demo RAG | Judge offline avaliando a resposta |
| `agent/guardrails/input_guardrail.py` | `check_input` | Demo PII | Regex de masking em ação |

---

## Comandos de emergência

```powershell
# Reiniciar cluster local (F5 no VS Code → "Cluster Local")

# Verificar se os serviços estão no ar
Invoke-RestMethod http://localhost:8000/docs   # Swagger UI
Invoke-RestMethod http://localhost:8001/docs   # Mock services Swagger

# Rodar demo completo via script
$env:PYTHONPATH = "."; .\venv\Scripts\python scripts/run_demo.py
```
