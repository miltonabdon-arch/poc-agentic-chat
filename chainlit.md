# PoC Agente de Catálogo TIM

Interface de demonstração do pipeline de agentes — valida a arquitetura
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci) em ambiente local.

Faça uma pergunta sobre planos, fatura, cancelamento ou ofertas. Cada nó do pipeline
aparece como step expansível com o JSON de saída em tempo real.

> **Pré-requisito:** gateway (`:8000`) e mock services (`:8001`) devem estar rodando.
