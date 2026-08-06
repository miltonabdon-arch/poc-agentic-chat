# Relatório de Aderência — `agent_platform_oci` (resumo)

> Resumo extraído de `relatorio-aderencia-agent-platform-oci.md` do
> repositório do projeto principal (análise datada de 2026-07-31, feita via
> leitura remota de README/documentação, sem clone local — ver
> `docs/referencias/README.md` deste repositório de PoC).

## O que foi analisado

O repositório público https://github.com/hoshikawa2/agent_platform_oci,
comparado contra o Escopo Técnico v1.2 e os designs do projeto principal —
para confirmar se `agent_platform_oci` é um framework real e maduro, ou uma
stack desconhecida/incompatível (risco B-006 do projeto principal).

## Conclusão central

`agent_platform_oci` é um framework corporativo real da Oracle — Python
(3.12/3.13) + FastAPI + LangGraph + Pydantic, com 20 especificações internas
(SPEC-001 a SPEC-020). Sua arquitetura bate ponto a ponto com o que os
designs do projeto principal já haviam desenhado por inferência, **antes**
de qualquer verificação do código real:

| Componente do design do projeto principal | Componente real em `agent_platform_oci` |
|---|---|
| Router central | Enterprise Router / Supervisor (LangGraph workflow) |
| Guardrails Input/Output | SPEC-005 (Guardrails — input/output/tools/RAG/final response) |
| Hook de Supervisão Inline | Nó de Router/Supervisor dentro do workflow LangGraph |
| Observability Tracer | Langfuse + OpenTelemetry (SPEC-007) |
| Audit Logger | Eventos IC/NOC/GRL (SPEC-007) |
| `AgentRuntimeMixin` | Classe real do framework (SPEC-002 — Agent Runtime) |
| Channel Gateway | SPEC-009 — normaliza payloads multi-canal para `GatewayRequest` |

ADW (`SESSION_REPOSITORY_PROVIDER=autonomous`) e OCI Generative AI
(`LLM_PROVIDER=oci_openai`) são confirmados como providers nativos no `.env`
de exemplo do framework — não apenas citações de texto.

## Risco remanescente (por que esta PoC existe)

A análise foi feita **apenas lendo documentação remota** (README, sem clone
nem execução). O risco que permanece — e que esta PoC reduz na parte que
está sob seu controle — é: a instância real do framework que a TIM/Oracle
vai provisionar corresponde ao repositório público analisado, ou há
fork/customização interna não verificável de fora? Esta PoC não resolve essa
pergunta (não é uma decisão que dependa de rodar código local), mas reduz o
risco associado à "base pública" ao efetivamente rodar o framework de ponta
a ponta.

## O que não foi possível avaliar (no relatório original)

- Código-fonte completo (`app/`, `config/*.yaml`, `libs/agent_framework/`)
- SPEC-008/017/020 na íntegra (deployment, release, SRE)
- Versão exata do framework que a TIM/Oracle vai disponibilizar

Ver `STATE.md` deste repositório de PoC, seção "Active Blockers", para o
tratamento desse risco no escopo desta PoC.
