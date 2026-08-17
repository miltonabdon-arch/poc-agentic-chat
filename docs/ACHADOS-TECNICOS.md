# Achados Técnicos — PoC Agente de Catálogo TIM

**Data:** 2026-08-17 · **Equipe:** CI&T / TIM Agentes de Atendimento
**Documento:** entregável §9 de `docs/CRITERIOS-DE-ACEITE.md`
**Referência:** análise documental prévia em `docs/referencias/relatorio-aderencia-agent-platform-oci-resumo.md`

---

## 1. O que funcionou como esperado

**Contratos do `agent_framework`.**
Os três contratos centrais do framework funcionaram exatamente como a análise
documental havia previsto:

- `ChannelMessage` (SPEC-003): normalizou a entrada do gateway sem nenhuma adaptação.
  O campo `session_id` foi suficiente para rastreabilidade de ponta a ponta.
- `EnterpriseRouter` (SPEC-004): roteamento por arquivo YAML sem nenhum código
  adicional — basta declarar os intents, keywords e o agente-alvo.
  Adicionou 7 intents em minutos.
- `AgentObserver` (SPEC-007-lite): a interface `emit(event_type, payload)` integrou
  sem falhas. Em modo noop (sem `analytics` nem `event_bus`) não lança exceção —
  o try/except do tracer captura e continua silenciosamente.

**Stack base (FastAPI + LangGraph + Chroma).**
Nenhum conflito de versão entre as dependências do framework e as da PoC.
`docker compose up` sobe o ambiente completo do zero, sem etapa manual adicional.

**Embedding multilíngue.**
O modelo `paraphrase-multilingual-MiniLM-L12-v2` discriminou corretamente nomes
de planos em português ("Turbo 40GB" vs "Controle 20GB") — o default do Chroma
(focado em inglês) teria colapsado esses embeddings. A recomendação da análise
documental de usar um modelo multilíngue se confirmou na prática.

**Re-ranking com CrossEncoder.**
`BAAI/bge-reranker-v2-m3` resolveu o caso de ambiguidade em que RAG retornava
o chunk de um plano parecido no top-1. Após re-ranking, a precisão subiu o
suficiente para o threshold de 0.7 funcionar sem falsos positivos nos cenários
de teste.

**Compatibilidade com Flow CI&T (LiteLLM proxy).**
O cliente OpenAI padrão com `default_headers` (`FlowTenant`, `FlowAgent`)
funcionou sem nenhuma adaptação adicional. O provider pode ser trocado apenas
alterando variáveis de ambiente — sem mudança de código.

---

## 2. O que exigiu adaptação

**Grafo LangGraph é sempre responsabilidade do desenvolvedor.**
O framework fornece `EnterpriseRouter` para roteamento, mas **não monta o
`StateGraph`**. A topologia (nós, arestas condicionais, `TypedDict` de estado)
deve ser construída explicitamente pelo AI Developer Sr. Para a PoC: 11 nós,
3 arestas condicionais, `GraphState` com 9 campos. No projeto real, essa
topologia crescerá com cada nova jornada de negócio — é um entregável contínuo,
não uma configuração pontual.

**`AgentObserver` em noop não produz logs locais.**
Em ambiente sem `analytics` nem `event_bus`, o `emit()` é executado mas não
imprime nada. A análise documental não havia antecipado que o modo noop seria
silencioso. Solução: adicionamos uma segunda camada de logging estruturado
(`TRACE|tipo|campo=valor`) em `orchestrator/tracer.py`. Essa camada não existe
no framework — é uma adição específica da PoC para atender §6 localmente.
No projeto real, o `AgentObserver` com Langfuse/OCI tornará essa camada
redundante.

**Vendoring do `agent_framework`.**
O pacote não está em PyPI público. A solução foi copiar
`agent_platform_oci/libs/agent_framework` para `vendor/agent_framework/`
(gitignored) e instalar via `pip install vendor/agent_framework` no Dockerfile.
No projeto real, isso deve ser resolvido com um índice PyPI interno ou
artefato no Container Registry OCI antes do início da implementação.

**`chunk_id` não propagado nativamente pelo framework.**
O `GraphState` padrão não carrega o identificador de documento RAG através
do grafo. Para atender §6 (chunk_id visível no trace), adicionamos o campo
`chunk_id: str | None` ao `GraphState` e alteramos `_run_catalog` para
retornar uma tupla `(resposta, chunk_id)`. Essa extensão não conflita com o
framework — é um campo adicional no TypedDict.

---

## 3. Gaps encontrados

**Integração paralela com branches do time (AD-008 → AD-009 → AD-010).**
A primeira tentativa de integrar o `agent_framework` (AD-008) causou conflitos
de merge enquanto os demais papéis ainda estavam trabalhando em branches
separadas. A solução (AD-009 + AD-010) foi reverter e reintroduzir via
vendoring após todas as fatias estarem integradas. No projeto real, recomenda-se
definir o pacote `agent_framework` como dependência explícita desde o kickoff
para evitar esse ciclo de reversão.

**Prazo de integração subestimado.**
O Checkpoint 1 (Dia 5 — ingestão + RAG ponta a ponta) foi entregue com ~8 dias
de atraso. As causas identificadas: (a) custo de validação do setup do framework
maior que o previsto, (b) coordenação entre branches paralelas sem contrato de
integração explícito desde o dia 1. Mitigação para o projeto real: estabelecer
interfaces e mocks de dados (QueryResult, GuardrailResult, ChannelMessage) no
kickoff, antes de qualquer código de implementação.

**Risco B-006 permanece (divergência instância OCI interna x repositório público).**
Esta PoC validou o framework a partir do repositório público
(`github.com/hoshikawa2/agent_platform_oci`). A divergência entre esse
repositório e a instância interna Oracle/TIM — se existir — não foi
investigada e permanece como risco para o projeto real. Recomendamos solicitar
acesso ao repositório interno antes do início da implementação.

---

## 4. Conclusão

A hipótese central da PoC se confirma: **é possível montar um agente
conversacional ponta a ponta sobre `agent_platform_oci` em 2 semanas, usando
apenas componentes locais e mock.** Os critérios §1-§6 e §8 de
`CRITERIOS-DE-ACEITE.md` foram atendidos. O risco técnico remanescente deixa
de ser "o framework funciona?" e passa a ser exclusivamente a questão de B-006
(instância interna OCI vs. repositório público).

Para o projeto real, os três pontos de atenção mais relevantes são:
(1) definir a topologia do grafo LangGraph desde o kickoff como artefato de
design, não apenas de código; (2) resolver o acesso ao `agent_framework`
como pacote interno antes do início; (3) investigar B-006 com Oracle/TIM.
