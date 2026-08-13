"""Vetorizador - ver docs/INGESTAO.md, secao 5.

Usa Chroma local como vector store, representando o papel do ADW no design
real (pipeline-rag-base/design.md).

TODO (Data Engineer): implementar get_client(), get_collection() e
vectorize_and_store() para satisfazer os testes de tests/test_ingestao.py.

Pontos de atenção (ver docs/INGESTAO.md para os achados de validação
originais desta PoC, que motivam estas escolhas):
- Modelo de embedding: o default do Chroma é focado em inglês e não
  discrimina bem nomes de planos parecidos em português — considere um
  modelo multilíngue.
- Métrica de distância: o default do Chroma (L2) não é diretamente
  interpretável como confidence_score em [0, 1] — considere configurar a
  métrica da collection explicitamente.
"""

import chromadb
from chromadb.utils import embedding_functions

from rag_pipeline.models import Chunk


_DEFAULT_COLLECTION = "catalogo_poc"


def get_client(persist_path: str = "./chroma_data") -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=persist_path)
    

def get_collection(client: chromadb.ClientAPI, name: str = _DEFAULT_COLLECTION):
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2",
            normalize_embeddings=True,
        ),
    )


def vectorize_and_store(client: chromadb.ClientAPI, chunk: Chunk, collection_name: str = _DEFAULT_COLLECTION) -> None:
    collection = get_collection(client, collection_name)
    collection.upsert(
        ids=[chunk.chunk_id],
        documents=[chunk.text],
        metadatas=[{
            "source_document_id": chunk.source_document_id,
            "plano_id": chunk.plano_id,
            "categoria": chunk.categoria,
            "vigencia_inicio": str(chunk.vigencia_inicio),
            "section": chunk.section,
            "nome_plano": chunk.nome_plano,
            "status": chunk.status,
        }],
    )


#Model options:
#paraphrase-multilingual-mpnet-base-v2
#paraphrase-multilingual-MiniLM-L12-v2