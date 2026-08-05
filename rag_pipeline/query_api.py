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

import chromadb

from rag_pipeline.models import QueryResult

_DEFAULT_COLLECTION = "catalogo_poc"
_DEFAULT_THRESHOLD = 0.5  # TODO (Data Engineer): calibrar empiricamente


def query(
    client: chromadb.ClientAPI,
    text: str,
    threshold: float = _DEFAULT_THRESHOLD,
    collection_name: str = _DEFAULT_COLLECTION,
) -> QueryResult:
    raise NotImplementedError
