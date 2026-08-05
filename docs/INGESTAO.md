# Documentação de Ingestão — Pipeline RAG da PoC

Responsável: **Data Engineer**. Este documento é o contrato entre o pipeline
de ingestão e o restante do time — qualquer papel que precise consumir o
vector store (AI Scientist, para a API de Consulta RAG) deve conseguir
entender o que está armazenado só lendo este documento.

## 1. Dado de entrada

Documentos sintéticos em Markdown, um por plano/oferta fictícia, em
`data/catalogo/`. Nenhum dado real da TIM — cada arquivo é fabricado para
esta PoC.

Estrutura de cada arquivo (`data/catalogo/<slug-do-plano>.md`):

```markdown
---
plano_id: turbo-40gb
nome: Plano Turbo 40GB
categoria: controle
vigencia_inicio: 2026-01-01
---

# Plano Turbo 40GB

## Franquia
40GB de internet 4G/5G, com 10GB adicionais em app parceiro.

## Fidelidade
Sem fidelidade contratual.

## Multa de cancelamento
Não se aplica (sem fidelidade).

## Elegibilidade
Disponível para clientes Controle com Score Crivo >= 600 (fictício).
```

O front-matter (`plano_id`, `nome`, `categoria`, `vigencia_inicio`) é
metadado obrigatório — usado no enriquecimento de chunk (seção 4). O corpo em
Markdown usa headers `##` para demarcar seções (Franquia, Fidelidade, Multa,
Elegibilidade) — o chunker (seção 3) fragmenta por essas seções.

Volume mínimo para a PoC: **8 a 12 documentos sintéticos**, cobrindo pelo
menos um plano de cada categoria citada no caso de uso (`PROPOSTA-POC.md`,
seção 4): Controle, Família, Pré-pago.

## 2. Extração de texto

Como os documentos de entrada já são Markdown puro (não PDF/DOCX escaneado),
a etapa de extração desta PoC **não inclui OCR** — isso é uma simplificação
deliberada em relação ao `pipeline-rag-base/design.md` do projeto real, que
precisa lidar com documentos reais de TIM X/Acquia em formatos variados.

`rag_pipeline/extractor.py` apenas lê o arquivo, separa front-matter (YAML)
do corpo (Markdown), e retorna:

```yaml
raw_text: string        # corpo em Markdown, sem o front-matter
metadata: dict           # front-matter parseado
source_document_id: string   # nome do arquivo, sem extensão
```

## 3. Chunking

Estratégia: **split por header Markdown** (`##`) — cada seção do documento
(Franquia, Fidelidade, Multa, Elegibilidade) vira um chunk independente.
Esta é a mesma estratégia `markdown_header` já prevista como opção em
`pipeline-rag-base/design.md` (Componente 3, Chunker).

Por que esta estratégia e não sliding window: os documentos sintéticos são
curtos e já estruturados por seção — dividir por header preserva o
significado de cada chunk sem precisar calibrar tamanho/overlap.

## 4. Enriquecimento de metadados

Cada chunk recebe, do front-matter do documento de origem:

```yaml
chunk_id: string           # <source_document_id>#<nome-da-secao>
text: string                # ver nota de "contextual chunk header" abaixo
source_document_id: string
plano_id: string
categoria: string
vigencia_inicio: string
section: string             # nome do header (ex.: "Franquia")
status: enum[active]         # esta PoC não implementa soft delete/curadoria
```

**Achado de validação — contextual chunk header:** a primeira versão desta
PoC vetorizava apenas o texto puro da seção (ex.: "40GB compartilhados entre
até 4 linhas..."), sem o nome do plano. Isso causava confusão de retrieval
entre planos com conteúdo parecido (ex.: perguntas sobre o "Plano Turbo
40GB" retornavam chunks do "Plano Família Essencial", que também menciona
"40GB"). A correção foi prefixar cada chunk com `"<nome do plano> - <seção>:
<texto>"` antes de vetorizar — técnica conhecida como *contextual chunk
header*. Qualquer ingestão de conteúdo real (TIM X/Acquia) no projeto
principal deve considerar a mesma prática.

## 4.1. Modelo de embedding

Esta PoC usa `paraphrase-multilingual-MiniLM-L12-v2` (via
`sentence-transformers`), não o modelo default do Chroma
(`all-MiniLM-L6-v2`, otimizado para inglês) — o modelo default demonstrou
discriminação fraca entre nomes de planos em português durante a validação
desta PoC. A escolha do modelo de embedding de produção continua sendo
decisão do projeto real (Open Question já registrada em
`pipeline-rag-base/design.md`).

## 5. Vetorização e armazenamento

- **Modelo de embedding:** qualquer modelo de embedding compatível com a API
  de LLM configurada (ver `.env.example`) — a escolha exata do modelo não é
  uma decisão crítica desta PoC, qualquer modelo de embedding de propósito
  geral serve
- **Armazenamento:** Chroma local (arquivo em `./chroma_data/`, criado pelo
  `docker-compose`), representando o papel do ADW no design real
- Cada chunk vetorizado é inserido com o `chunk_id` como identificador único
  — reinserir o mesmo `chunk_id` substitui o chunk anterior (upsert), o que
  torna a ingestão idempotente

## 6. Como rodar a ingestão

```bash
pip install -r requirements.txt
python scripts/run_ingestao.py --input data/catalogo/ --collection catalogo_poc
```

O Chroma roda embutido no processo Python (`chromadb.PersistentClient`,
persistindo em `./chroma_data/`) — não há serviço separado para subir antes.

O script:
1. Lê todos os `.md` de `data/catalogo/`
2. Aplica extração → chunking → enriquecimento → vetorização (seções 2-5)
3. Imprime um resumo: quantos documentos, quantos chunks, quantos segundos

Saída esperada (exemplo):

```
Ingestão concluída: 10 documentos, 34 chunks, 4.2s
Collection: catalogo_poc (Chroma local, ./chroma_data/)
```

## 7. Consulta (contrato consumido pelo AI Scientist)

A API de Consulta RAG (`rag_pipeline/query_api.py`, entregue pelo Data
Engineer mas consumida pelo AI Scientist na construção do prompt) expõe:

```python
def query(text: str, threshold: float = 0.35) -> QueryResult:
    ...
```

Retorno:

```yaml
found: boolean
chunk_id: string | null
text: string | null
source_document_id: string | null
confidence_score: number
```

Mesma estrutura de contrato usada em `pipeline-rag-base/design.md`
(`QueryResult`) — abaixo do `threshold`, `found: false` é retornado
explicitamente, nunca uma resposta inventada.

**Threshold default (`0.65`):** calibrado empiricamente contra
`data/catalogo/` — perguntas dentro do catálogo sintético pontuaram
confidence 0.69-0.85, perguntas fora do catálogo pontuaram 0.39-0.61; 0.65
separa os dois grupos nesta amostra específica. Este valor precisa ser
recalibrado se o catálogo real (TIM X/Acquia) tiver uma distribuição de
similaridade diferente — é um valor de PoC, não uma constante definitiva
(mesma ressalva que `pipeline-rag-base/design.md` já registra como Open
Question para o projeto real).

## 8. Testes de ingestão (responsabilidade do Data Engineer)

`tests/test_ingestao.py` deve cobrir, no mínimo:
- Um documento com todas as seções esperadas gera o número correto de chunks
- Um documento sem uma seção opcional (ex.: sem "Multa") não quebra a
  ingestão, apenas gera menos chunks
- Reingerir o mesmo documento não duplica chunks (upsert por `chunk_id`)
- Uma consulta por termo presente em um chunk retorna `found: true` com
  `confidence_score` acima do threshold default
- Uma consulta por termo ausente de todo o catálogo retorna `found: false`
