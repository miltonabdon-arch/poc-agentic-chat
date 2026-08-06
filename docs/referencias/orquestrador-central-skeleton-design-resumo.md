# Orquestrador Central (Skeleton) — Design (resumo)

> Resumo extraído de
> `.specs/features/orquestrador-central-skeleton/design.md` do repositório
> do projeto principal. Contém apenas os pontos que `docs/ARQUITETURA.md`
> desta PoC referencia diretamente — ver `docs/referencias/README.md`.

## O que é, no projeto real

Skeleton do orquestrador do Agente POV: um Router `agent_platform_oci`
central com dois middlewares obrigatórios (Camada 1: Guardrails de Input e
Output) envolvendo toda chamada ao LLM, roteando entre as 5 jornadas de
negócio (Informação, Ativação, Mudança de Plano, Cancelamento — mais o
subfluxo de handoff do Agente de Contas), com observabilidade e auditoria
transversais.

## Contrato `GuardrailResult` (citado em `docs/ARQUITETURA.md`)

```yaml
guardrail_type: enum[input, output]
violation: enum[pii, toxic_content, competitor_mention, out_of_domain, none]
action_taken: enum[block, mask, substitute, shadow_log, allow]
```

Esta PoC usa a mesma estrutura, com um subconjunto menor de `violation`
(apenas `pii`, `competitor_mention`, `out_of_domain`, `none` — sem
`toxic_content`, fora do escopo desta PoC) e de `action_taken` (apenas
`block`, `mask`, `allow` — sem `substitute`/`shadow_log`).

## Componentes do design real mapeados na PoC (`docs/ARQUITETURA.md`)

| Componente do design real | Equivalente nesta PoC | Simplificação |
|---|---|---|
| Router `agent_platform_oci` | Router / Grafo LangGraph (`orchestrator/graph.py`) | Sem roteamento entre múltiplas jornadas — só um único fluxo de consulta |
| Middleware de Guardrails Input/Output | Guardrails Input/Output desta PoC | Regras determinísticas simples (regex/lista), não o classificador leve completo do design real |
| Observability Tracer | Observability Tracer desta PoC | OpenTelemetry local (console/arquivo), sem Langfuse gerenciado nem eventos IC/NOC/GRL reais |
| Hook de Supervisão Inline (Camada 2) | **Não implementado nesta PoC** | Fora do escopo — ver `docs/PROPOSTA-POC.md`, seção 5 ("Camada 2 não incluída") |
| Audit Logger | **Não implementado nesta PoC** | Trilha de auditoria imutável é responsabilidade do projeto real, não desta PoC |

## Por que isso importa

Qualquer aprendizado desta PoC sobre o contrato `GuardrailResult` — como ele
se comporta na prática, que campos fazem sentido, onde a implementação
mínima já é suficiente — é diretamente reaproveitável no projeto real,
porque o vocabulário é deliberadamente o mesmo.
