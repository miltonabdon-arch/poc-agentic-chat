# Pipeline RAG Base — Design (resumo)

> Resumo extraído de `.specs/features/pipeline-rag-base/design.md` do
> repositório do projeto principal. Contém apenas os pontos que
> `docs/INGESTAO.md` desta PoC referencia diretamente — ver
> `docs/referencias/README.md`.

## O que é, no projeto real

Pipeline de ingestão RAG do Agente POV: documento (fonte real — TIM
X/Acquia) → extração de texto (+ OCR quando necessário) → higienização →
chunking (estratégia configurável) → enriquecimento de metadados →
vetorização → **ADW** (Autonomous Data Warehouse, não Chroma). Além da
ingestão, o design real também prevê uma API de Curadoria (CRUD sobre
chunks, com re-vetorização granular e Audit Log) — **fora do escopo desta
PoC**.

## Pontos citados por `docs/INGESTAO.md` desta PoC

**1. Extração/OCR (INGESTAO.md, seção 2).** O design real precisa lidar com
documentos reais em PDF/DOCX/HTML/TXT, incluindo OCR para conteúdo
digitalizado. Esta PoC usa documentos sintéticos já em Markdown puro — a
etapa de OCR é uma simplificação deliberada, não algo a implementar aqui.

**2. Estratégia de chunking (INGESTAO.md, seção 3).** O design real prevê 3
estratégias configuráveis: `sliding_window` (com overlap), `markdown_header`
(split por header) e `semantic`. Esta PoC usa apenas `markdown_header`,
porque os documentos sintéticos são curtos e já estruturados por seção —
não é preciso calibrar tamanho/overlap como seria necessário com
`sliding_window`.

**3. Modelo de embedding (INGESTAO.md, seção 4.1).** O design real trata a
escolha do modelo de embedding de produção como Open Question ainda não
resolvida — não é um valor fixo herdado do projeto principal. Esta PoC
escolheu `paraphrase-multilingual-MiniLM-L12-v2` apenas para os fins da PoC
(discriminação melhor em português do que o modelo default do Chroma); essa
escolha **não é uma recomendação de produção**.

**4. Contrato `QueryResult` (INGESTAO.md, seção 7).** O design real define:

```yaml
found: boolean
chunk_id: string | null
text: string | null
source_document_id: string | null
effective_date: string | null   # esta PoC omite este campo (não há vigência no catálogo sintético)
confidence_score: number
```

Mesma estrutura core (`found`/`chunk_id`/`text`/`source_document_id`/
`confidence_score`) usada nesta PoC — qualquer aprendizado sobre esse
contrato aqui é diretamente reaproveitável no projeto real.

**5. Threshold de confiança (INGESTAO.md, seção 7).** O design real também
trata isso como Open Question — nenhum valor foi definido, a ser calibrado
com dados reais de uso. Esta PoC não recebe (nem deveria) um valor calibrado
pronto do projeto real — cada time deve calibrar empiricamente contra o
próprio catálogo sintético (ver nota em `docs/INGESTAO.md` sobre a correção
aplicada em `rag_pipeline/query_api.py`, que removeu um valor hardcoded).

## O que esta PoC deliberadamente não implementa do design real

- Extrator com suporte a PDF/DOCX/HTML/TXT + OCR
- API de Curadoria (CRUD de chunks, soft delete, Audit Log de edição)
- ADW como armazenamento (usa Chroma local)
- Campo `effective_date` no contrato de chunk
