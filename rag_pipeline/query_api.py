"""API de Consulta RAG - ver docs/INGESTAO.md, secao 7.

Contrato consumido pelo AI Scientist ao construir o prompt do agente.
Segue o mesmo formato de QueryResult descrito em pipeline-rag-base/design.md
do projeto real (found/source/confidence).

TODO (Data Engineer): implementar query() para satisfazer os testes de
tests/test_ingestao.py.

Contrato (ver QueryResult em rag_pipeline/models.py):
- Consultar a collection por similaridade com o texto de entrada
- found=False (com chunk_id/text/source_document_id=None) se não houver
  candidato acima do threshold, ou se a collection estiver vazia
- confidence_score deve ser interpretável em [0, 1] (depende da métrica de
  distância configurada em vectorizer.get_collection())
- Atenção ao risco descrito em docs/INGESTAO.md, seção 7: perguntas fora do
  catálogo não devem "casar" por acidente com o chunk mais próximo — ver
  tests/test_ingestao.py, test_consulta_fora_do_catalogo_nao_inventa_resposta,
  e a discriminação entre planos parecidos em
  test_consulta_discrimina_planos_com_conteudo_parecido.
- _DEFAULT_THRESHOLD precisa ser calibrado empiricamente (ver
  docs/INGESTAO.md, seção 7) — o valor abaixo é só um placeholder inicial.
"""

import math

import chromadb
from sentence_transformers import CrossEncoder

from rag_pipeline.models import QueryResult
from rag_pipeline.vectorizer import get_collection

_DEFAULT_COLLECTION = "catalogo_poc"
_DEFAULT_THRESHOLD = 0.60  # calibrado empiricamente: bge-reranker-v2-m3 em português dá scores em ~0.55–0.70 para matches relevantes
_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(_RERANKER_MODEL, device="cpu")
    return _reranker


def _rerank(query_text: str, candidates: list[dict]) -> tuple[dict, float]:
    pairs = [(query_text, c["text"]) for c in candidates]
    scores = _get_reranker().predict(pairs)
    normalized = [1 / (1 + math.exp(-float(s))) for s in scores]
    best_idx = max(range(len(normalized)), key=lambda i: normalized[i])
    return candidates[best_idx], normalized[best_idx]


def query(
    client: chromadb.ClientAPI,
    text: str,
    threshold: float = _DEFAULT_THRESHOLD,
    collection_name: str = _DEFAULT_COLLECTION,
) -> QueryResult:
    collection = get_collection(client, collection_name)

    if collection.count() == 0:
        return QueryResult(found=False, chunk_id=None, text=None, source_document_id=None, confidence_score=0.0)

    n = min(5, collection.count())
    results = collection.query(query_texts=[text], n_results=n, include=["documents", "metadatas", "distances"])

    candidates = [
        {
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]
    
    best, confidence_score = _rerank(text, candidates)

    if confidence_score < threshold:
        return QueryResult(found=False, chunk_id=None, text=None, source_document_id=None, confidence_score=confidence_score)

    return QueryResult(
        found=True,
        chunk_id=best["id"],
        text=best["text"],
        source_document_id=best["metadata"]["source_document_id"],
        confidence_score=confidence_score,
    )
