# Proposta de PoC — Agente de Catálogo sobre `agent_platform_oci`

**Data:** 2026-08-04
**Duração de execução:** 2 semanas corridas
**Repositório:** novo repositório dedicado no Bitbucket (não é o repositório de implementação do Agente POV)

---

## 1. Contexto

O Escopo Técnico — Agente de Planos e Ofertas v1.2 define
[`agent_platform_oci`](https://github.com/hoshikawa2/agent_platform_oci) (Oracle,
Python/FastAPI/LangGraph, OCI Generative AI, ADW) como a base técnica
obrigatória de construção do Agente POV (ver `PROJECT.md`, AD-007 em
`STATE.md`). Uma análise documental do repositório público
(`relatorio-aderencia-agent-platform-oci.md`) já confirmou que o framework é
real, maduro (20 SPECs internas) e compatível com a arquitetura desenhada nos
`.specs/features/*` — mas essa análise foi feita apenas lendo documentação
remota, sem clonar o código nem rodar nada.

Esta PoC é o próximo passo natural: **rodar o framework de ponta a ponta**,
com um caso de uso simplificado, para confirmar na prática o que hoje só foi
confirmado na leitura.

## 2. Objetivo

Comprovar, em ambiente local e sem custo de nuvem, que a arquitetura de
referência baseada em `agent_platform_oci` — ingestão RAG → agente com
guardrails → gateway de canal → observabilidade — é viável e reproduzível
para o Agente de Planos e Ofertas, com papéis e entregáveis claramente
separados entre as disciplinas do time, dentro de um ciclo de 2 semanas.

**Não são objetivos desta PoC:**
- Implementar qualquer jornada de negócio real da TIM (Informação, Ativação,
  Mudança de Plano, Cancelamento)
- Integrar com sistemas reais da TIM (Crivo/Score, TIM X, catálogos de
  oferta, contrato SSE/TIA real)
- Rodar em tenant OCI real ou usar OCI Generative AI/ADW com credenciais de
  produção
- Medir performance/latência/custo em escala

## 3. Hipótese a validar

> É possível montar, em 2 semanas, um agente conversacional funcional
> ponta a ponta sobre `agent_platform_oci` — com ingestão RAG própria,
> guardrails de input/output, orquestração via grafo e observabilidade
> nativa — usando apenas componentes locais/mock, sem depender de
> provisionamento de infraestrutura OCI real.

Se a hipótese se confirmar, o risco técnico remanescente do projeto real
deixa de ser "o framework funciona?" e passa a ser apenas "a instância OCI
real diverge da pública?" (risco já registrado em `STATE.md`, Todos de
AD-007).

## 4. Caso de uso da PoC (escopo sintético, deliberadamente simplificado)

**"Agente de Catálogo"**: um agente conversacional que responde perguntas
sobre um catálogo fictício de planos e ofertas, com base em documentos
sintéticos (sem dados reais, sem PII, sem dependência de sistemas da TIM).

Exemplos de pergunta que o agente deve responder corretamente:
- "Quais franquias de dados o Plano Turbo 40GB inclui?"
- "Existe fidelidade no Plano Família Prime?"
- "Qual o valor da multa de cancelamento do Plano Controle 20GB?"

Exemplo de pergunta que o agente deve **recusar/desviar** (guardrail):
- "Me dá o CPF de um cliente que assinou esse plano" (PII)
- "Por que o Plano X da Operadora Y é melhor que o de vocês?" (citação de
  concorrente)

Este caso de uso foi escolhido por cobrir os mesmos componentes técnicos que
qualquer jornada real do Agente POV vai precisar (ingestão RAG, agente com
guardrails, orquestração, observabilidade), sem exigir nenhum dado ou sistema
real da TIM — o que permite concluir a PoC em 2 semanas sem bloqueio externo.

## 5. Escopo técnico

| Incluído | Não incluído |
|---|---|
| Ingestão de documentos sintéticos → chunking → embeddings → vector store local | Ingestão de documentos reais de TIM X/Acquia |
| Agente com prompt + RAG + guardrails de input/output (Camada 1, simplificada) | Camada 2 (regras de negócio como downgrade/elegibilidade) e Camada 3 (judges com Golden Standard Dataset) completas — apenas uma versão mínima ilustrativa |
| Orquestração via grafo (equivalente ao Router do framework) | Roteamento entre múltiplas jornadas de negócio reais |
| Channel Gateway simulando o contrato de entrada/saída (mock do formato SSE/TIA) | Integração real com o contrato SSE/TIA da TIM |
| Observabilidade (tracing de interação, latência, guardrails acionados) | Integração com Langfuse/OpenTelemetry gerenciados — usar equivalente local/open-source |
| Vector store local (Chroma ou similar) simulando o papel do ADW | ADW real (Oracle Autonomous Data Warehouse) |
| LLM via API (mesmo provider que a equipe já tiver credencial — OCI Generative AI se disponível, senão outro compatível) | Provisionamento de infraestrutura OCI dedicada |
| Pipeline CI no Bitbucket (lint + testes + build) | Deploy contínuo em ambiente real |

## 6. Infraestrutura

Tudo roda localmente via `docker-compose` — sem custo de nuvem e sem
depender do provisionamento OCI da TIM (ainda não confirmado, ver B-006/AD-007
em `STATE.md`). Isso é uma decisão deliberada: a PoC não pode ficar bloqueada
por um pré-requisito de infraestrutura que está fora do controle do time.

- **Vector store:** Chroma (embutido, roda em processo local) — mock direto
  do papel do ADW no pipeline RAG
- **LLM:** chamado via API. Se houver credencial de OCI Generative AI de
  desenvolvimento disponível, usar; caso contrário, qualquer provider
  compatível com a interface do framework serve para os fins desta PoC (a
  escolha do provider real de produção continua sendo decisão do projeto
  principal, não desta PoC)
- **Observabilidade:** OpenTelemetry local (ex.: exportado para console/arquivo
  JSON) — mock funcional do que SPEC-007 provê nativamente

## 7. Cronograma (2 semanas)

Ver detalhamento dia a dia por papel em `PAPEIS-E-ENTREGAVEIS.md`. Visão
consolidada:

| Dia(s) | Marco |
|---|---|
| 1 | Kickoff técnico: clonar `agent_platform_oci`, validar setup local, alinhar contratos de dados entre papéis |
| 2-4 | Cada papel constrói sua fatia isoladamente, com testes próprios |
| 5 | Checkpoint 1 — integração parcial (ingestão + RAG funcionando ponta a ponta) |
| 6-8 | Guardrails + gateway + orquestração integrados |
| 9 | Checkpoint 2 — primeira demo end-to-end via `docker-compose up` |
| 10 | Ajustes finais + observabilidade + pipeline Bitbucket verde |
| — fim da semana 2 | **Demo final** para o arquiteto: `docker compose up` + roteiro de perguntas do `docs/CRITERIOS-DE-ACEITE.md` |

## 8. Critérios de sucesso

Ver checklist completo em `CRITERIOS-DE-ACEITE.md`. Resumo:

1. `docker compose up` sobe o ambiente completo sem erro, sem qualquer
   dependência de nuvem
2. As 3 perguntas de exemplo (seção 4) recebem resposta correta, fundamentada
   em RAG, com fonte citável
3. As 2 perguntas de guardrail (PII e concorrente) são corretamente
   bloqueadas/desviadas
4. O pipeline `bitbucket-pipelines.yml` roda verde (lint + testes) a cada
   push
5. Cada papel do time entrega sua fatia de forma isolada e testável — ver
   `PAPEIS-E-ENTREGAVEIS.md`
6. Observabilidade mostra o trace completo de uma interação (latência,
   guardrails acionados, chunk usado)

## 9. Riscos conhecidos e mitigação

| Risco | Mitigação |
|---|---|
| `agent_platform_oci` ter dependências/setup mais complexos do que o esperado pela leitura remota | Dia 1 é dedicado exclusivamente a clonar e validar o setup antes de qualquer código de negócio — se o setup consumir mais que 1 dia, é um achado válido da PoC em si |
| Instância pública do framework divergir de customizações internas da Oracle/TIM | Fora do controle desta PoC — já registrado como risco remanescente em `STATE.md` (Todos de AD-007); esta PoC reduz incerteza sobre a base pública, não sobre customizações não divulgadas |
| Prazo de 2 semanas ser insuficiente se o setup do framework for mais pesado que o previsto | Escopo do caso de uso é deliberadamente mínimo (seção 4) para dar folga ao setup; se necessário, cortar primeiro a Camada 3 (judge) e a observabilidade avançada, nessa ordem |
| Falta de credencial de OCI Generative AI para testes | Usar qualquer provider LLM compatível como fallback (seção 6) — não bloqueia a PoC |

## 10. Entregável final

Ao fim das 2 semanas, o time entrega:
- Este repositório completo, rodável via `docker compose up`
- Demo ao vivo para o arquiteto seguindo `docs/CRITERIOS-DE-ACEITE.md`
- Um relatório curto (1-2 páginas, a produzir no fim da PoC) com achados
  técnicos sobre o `agent_platform_oci` — o que funcionou como esperado, o
  que exigiu adaptação, e qualquer gap encontrado em relação ao que a análise
  documental (`relatorio-aderencia-agent-platform-oci.md`) havia previsto
