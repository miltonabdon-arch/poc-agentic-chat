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

from rag_pipeline.models import Chunk

_DEFAULT_COLLECTION = "catalogo_poc"


def get_client(persist_path: str = "./chroma_data") -> chromadb.ClientAPI:
    raise NotImplementedError


def get_collection(client: chromadb.ClientAPI, name: str = _DEFAULT_COLLECTION):
    raise NotImplementedError


def vectorize_and_store(client: chromadb.ClientAPI, chunk: Chunk, collection_name: str = _DEFAULT_COLLECTION) -> str:
    raise NotImplementedError
