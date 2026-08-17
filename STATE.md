# State

**Last Updated:** 2026-08-17
**Escopo deste arquivo:** este `STATE.md` é local a este repositório (PoC de 2
semanas do "Agente de Catálogo"). Ele **não substitui** o `STATE.md` do
projeto principal do Agente de Planos e Ofertas (POV).

**Current Work:** PoC funcional ponta a ponta. Demo de 5 casos validada via
HTTP e via `scripts/run_demo.py` com LLM real (Flow CI&T / gpt-4o-mini).
Branch `feature/orchestrator-agentframework-native` está pronta para PR na
`main`. Apresentação agendada para 2026-08-18.

---

## Status dos Módulos (2026-08-17)

| Módulo | Status | Responsável |
|---|---|---|
| `rag_pipeline/vectorizer.py` | ✅ Implementado | Data Engineer (Ana) |
| `rag_pipeline/query_api.py` | ✅ Implementado (CrossEncoder re-ranking) | Data Engineer (Ana) |
| `rag_pipeline/extractor.py` | ✅ Implementado | Data Engineer (Ana) |
| `agent/judge.py` | ✅ Implementado | AI Scientist (Gustavo) |
| `agent/prompt.py` | ✅ Implementado | AI Scientist (Gustavo) |
| `agent/guardrails/input_guardrail.py` | ✅ Implementado (PII + out-of-domain) | AI Scientist (Gustavo) |
| `agent/guardrails/output_guardrail.py` | ✅ Implementado (context-leak + competitor + format) | AI Scientist (Gustavo) |
| `agent/llm_client.py` | ✅ Implementado + Flow CI&T headers | AI Dev Sr (Igor) |
| `gateway/app.py` | ✅ Implementado | Backend (Kirllen) |
| `gateway/channel_gateway.py` | ✅ Implementado | Backend (Kirllen) |
| `orchestrator/graph.py` — `run_interaction()` | ✅ Implementado (LangGraph real) | AI Dev Sr (Igor/Milton) |
| `orchestrator/graph.py` — `build_graph()` | ✅ Implementado (11 nós, 3 arestas condicionais) | AI Dev Sr (Igor/Milton) |
| `mock_services/` | ✅ Implementado (cancellation, deals, plans, CRM) | Backend (Kirllen) |

## Checkpoints da PoC

- [x] **Checkpoint 1 (Dia 5):** ingestão + RAG ponta a ponta — **concluído** (atrasado, entregue até Dia 13)
- [x] **Checkpoint 2 (Dia 9):** demo end-to-end via HTTP — **concluído** (5/5 casos passando, 2026-08-17)
- [ ] **Demo final + relatório:** apresentação em 2026-08-18

## Resultados da demo validada (2026-08-17)

```
[1/5] [Catálogo] Quais franquias de dados o Plano Turbo 40GB inclui?
      → RAG + LLM: "O Plano Turbo 40GB inclui 40GB de internet 4G/5G e oferece
        10GB adicionais em um aplicativo parceiro fictício (NetFlow)..."

[2/5] [Catálogo] Existe fidelidade no Plano Família Prime?
      → RAG + LLM: "Sim, o Plano Família Prime possui fidelidade de 24 meses.
        Nos primeiros 6 meses, você recebe bônus de 10GB adicionais."

[3/5] [Fora catálogo] Qual o preço do Plano Estratosférico 500GB?
      → not_found_response() ✓ (plano inexistente no catálogo)

[4/5] [Cancelamento] Quero cancelar minha linha.
      → handoff mock: "[Agente Retenção] Entendo que deseja cancelar..."

[5/5] [PII masking] Meu CPF é 123.456.789-00, qual meu plano atual?
      → CPF mascarado pelo input_guardrail antes do LLM ✓
```

## Testes (2026-08-17)

- **29 testes unitários:** 100% passando (`pytest -m "not integration"`)
- **5 testes de integração HTTP:** 100% passando via `scripts/test_http.ps1`
- CI: ruff ✓ → pytest ✓ → docker build ✓

---

## Recent Decisions

### AD-010: Vendorizar `agent_framework` para destravar integração real (2026-08-17)

**Decision:** Copiar `agent_platform_oci/libs/agent_framework` para
`vendor/agent_framework/` (gitignored) e instalar via `pip install vendor/agent_framework`
no Dockerfile. `orchestrator/graph.py` e `gateway/app.py` importam
`ChannelMessage`, `EnterpriseRouter` e `AgentObserver` do pacote real.

**Reason:** AD-009 reverteu a integração do framework para destravar merges
do time. Com todas as fatias agora implementadas e mescladas na branch
`feature/orchestrator-agentframework-native`, a integração real pôde ser
reintroduzida sem conflitos.

**Impact:** o objetivo central da PoC (validar o framework `agent_platform_oci`
em ambiente local) está **realizado**. `EnterpriseRouter` roteia via YAML,
`ChannelMessage` é o contrato de canal, `AgentObserver` emite traces.

---

### AD-009: Reverter AD-008 — integração real do `agent_framework` desfeita (2026-08-10)

**Decision:** Reverter o commit `3e80828` (AD-008) na `main` para destravar
merge do trabalho de `gbezerra-ciandt` (`test_new_branch`).
**Resolution:** resolvido em 2026-08-17 via AD-010 (vendoring).

---

### AD-007: Adotar `agent_platform_oci` como base técnica obrigatória (2026-07-31)

**Decision:** Framework confirmado como premissa obrigatória para o projeto real.
**Resolution:** validado por esta PoC — framework rodando ponta a ponta em ambiente local.

---

## Active Blockers

Nenhum blocker ativo. PoC funcional para apresentação.

### B-006 (rebaixado): Divergência entre instância OCI real e repositório público

**Status:** não bloqueia esta PoC. Risco remanescente para o projeto real —
depende de confirmação da TIM/Oracle sobre a instância interna.

---

## Todos

- [x] Mesclar `backend` (Kirllen) na `main` — PR #1, 2026-08-11
- [x] Mesclar `test_new_branch` (Gustavo) na `feature/orchestrator-agentframework-native` — 2026-08-17
- [x] Integração real do `agent_framework` via vendoring — AD-010, 2026-08-17
- [x] Integração Flow CI&T LiteLLM (`LLM_BASE_URL`, `FLOW_TENANT`, `FLOW_AGENT`) — 2026-08-17
- [x] Demo ponta a ponta validada — 5/5 casos, 2026-08-17
- [x] 29 testes unitários verdes — 2026-08-17
- [ ] **PR: `feature/orchestrator-agentframework-native` → `main`** (próximo passo)
- [ ] Relatório de achados técnicos sobre o `agent_platform_oci` (pós-apresentação)
- [ ] Judge leve com Golden Standard Dataset completo (Deferred — projeto real)
- [ ] State Store real compartilhado (Deferred — projeto real)
