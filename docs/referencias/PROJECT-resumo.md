# PROJECT.md (projeto principal) — resumo relevante para esta PoC

> Resumo extraído de `.specs/project/PROJECT.md` do repositório do projeto
> principal. Ver nota em `docs/referencias/README.md`.

## O que é o projeto principal

"Agente de Planos e Ofertas (POV)" — agente de IA conversacional e
transacional que automatiza as jornadas de Informação, Ativação, Mudança de
Plano (Up/Down) e Cancelamento de planos e ofertas da TIM, para clientes em
autoatendimento (mensageria digital e voz via URA) e atendentes humanos
(ATH) que recebem handoff qualificado do agente.

## Tech Stack (trecho relevante)

- Orquestração de agentes: **`agent_platform_oci`** — framework de Agentes
  da Oracle sobre OCI (orquestração, gateways de canal/IA/MCP, supervisão,
  guardrails, judges, memória, observabilidade)
- LLM: modelos dedicados via **OCI Generative AI**
- RAG / Vetor: **Vector Database corporativo — ADW** (Oracle Autonomous
  Data Warehouse)
- Canais: gateway de mensagens digitais (texto) + voz via URA, consumida
  exclusivamente via contrato SSE padrão TIA (`GET`/`POST /agent/sse`)

## Por que isso importa para esta PoC

**Stack confirmada como base técnica obrigatória (AD-007 — ver `STATE.md`
deste repositório de PoC):** o design anterior do projeto principal assumia
uma stack diferente (LangGraph/LangChain, Llama Dedicated AI, pgVector,
GCP). Essa stack foi substituída por instrução do usuário do projeto
principal: `agent_platform_oci`/OCI Generative AI/ADW é a premissa e base
obrigatória de construção de todos os agentes já especificados — não mais
uma hipótese pendente de confirmação.

Uma análise de aderência do repositório real do framework confirmou que é
maduro e documentado (20 SPECs internas), com arquitetura que já bate com o
que os designs do projeto principal haviam desenhado por inferência — ver
`relatorio-aderencia-agent-platform-oci-resumo.md` nesta mesma pasta.

**Esta PoC existe justamente para validar essa premissa na prática** —
rodar o framework de ponta a ponta, não apenas confirmar por leitura de
documentação (ver `docs/PROPOSTA-POC.md`, seção 1, deste repositório).

Stack majoritariamente **imposta pelo Framework Agreement TIM×Oracle**
(cliente), não decisão livre do time de implementação.
