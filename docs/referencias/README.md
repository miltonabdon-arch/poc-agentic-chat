# Referências externas (projeto principal)

Os documentos desta pasta **não são specs desta PoC** — são resumos extraídos
de documentos do repositório do **projeto principal** (Agente de Planos e
Ofertas / POV), citados por `docs/PROPOSTA-POC.md`, `docs/ARQUITETURA.md` e
`docs/INGESTAO.md` mas que vivem fora deste repositório dedicado à PoC.

Cada arquivo aqui contém apenas o recorte necessário para entender a
citação — não o documento completo do projeto principal (que inclui
decisões de escopo de negócio, propostas comerciais e histórico de projeto
sem relação com esta PoC técnica).

| Arquivo aqui | Original no projeto principal | Por que é citado |
|---|---|---|
| [`PROJECT-resumo.md`](PROJECT-resumo.md) | `.specs/project/PROJECT.md` | Contexto de por que `agent_platform_oci` é a base técnica obrigatória |
| [`relatorio-aderencia-agent-platform-oci-resumo.md`](relatorio-aderencia-agent-platform-oci-resumo.md) | `relatorio-aderencia-agent-platform-oci.md` | Análise documental que validou o framework antes desta PoC existir |
| [`pipeline-rag-base-design-resumo.md`](pipeline-rag-base-design-resumo.md) | `.specs/features/pipeline-rag-base/design.md` | Base das decisões de chunking, threshold e contrato `QueryResult` em `docs/INGESTAO.md` |
| [`orquestrador-central-skeleton-design-resumo.md`](orquestrador-central-skeleton-design-resumo.md) | `.specs/features/orquestrador-central-skeleton/design.md` | Base do contrato `GuardrailResult` e do desenho do Router em `docs/ARQUITETURA.md` |
| [`integracao-sse-tia-spec-resumo.md`](integracao-sse-tia-spec-resumo.md) | `.specs/features/integracao-sse-tia/spec.md` | Por que o Channel Gateway desta PoC é um mock — o contrato real depende do "Adendo A", ainda ausente |

Se o time precisar do documento completo (não apenas o resumo), solicitar
acesso ao repositório do projeto principal — esses resumos existem só para
que as citações nos docs desta PoC não sejam links quebrados.
