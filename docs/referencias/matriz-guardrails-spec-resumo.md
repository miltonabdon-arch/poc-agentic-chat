# Matriz de Guardrails (3 Camadas) — Spec (resumo)

> Resumo extraído de `.specs/features/matriz-guardrails/spec.md` do
> repositório do projeto principal. Citado apenas de passagem em
> `docs/ARQUITETURA.md` desta PoC (visão geral) — ver
> `docs/referencias/README.md`.

## O que é, no projeto real

Especifica as regras de negócio concretas que o Hook de Supervisão Inline do
orquestrador do projeto real invoca, organizadas em 3 camadas (vocabulário
do Escopo Técnico v1.2, item 6):

- **Camada 1 (Guardrails):** mascaramento de PII, detecção de
  toxicidade/tema fora do domínio, bloqueio de citação de concorrentes por
  nome
- **Camada 2 (Supervisão Inline):** bloqueio de sugestão de downgrade
  indevida, bloqueio de aplicação de plano/oferta fora da elegibilidade
  consultada
- **Camada 3 (Judges):** avaliação offline/amostragem, métricas NOC/ICC,
  correção de tom/voz

## Por que esta PoC só implementa a Camada 1 (versão mínima)

`docs/PROPOSTA-POC.md` (seção 5) já deixa explícito: esta PoC cobre apenas
"Agente com prompt + RAG + guardrails de input/output (Camada 1,
simplificada)" — Camada 2 (regras de negócio como downgrade/elegibilidade) e
Camada 3 (judges com Golden Standard Dataset) completas **não são objetivo
desta PoC**, apenas uma versão mínima ilustrativa do judge (ver
`agent/judge.py`).

Isso não é uma lacuna desta PoC — é escopo deliberado: as regras de negócio
específicas (downgrade, elegibilidade) dependem de conceitos do domínio real
da TIM (planos, ofertas, Crivo/Score) que o catálogo sintético desta PoC não
modela.
