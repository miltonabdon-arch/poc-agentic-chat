"""Enriquecedor de metadados - ver docs/INGESTAO.md, secao 4.

TODO (Data Engineer): implementar enrich() para satisfazer os testes de
tests/test_ingestao.py.

Contrato (ver Chunk em rag_pipeline/models.py):
- chunk_id = f"{document.source_document_id}#{section}"
- plano_id, categoria, vigencia_inicio vêm de document.metadata
- nome_plano vem de document.metadata["nome"]
- Atenção ao achado de validação descrito em docs/INGESTAO.md, seção 4:
  o texto vetorizado precisa de contexto suficiente (nome do plano + seção)
  para que perguntas sobre planos com conteúdo parecido não se confundam
  no retrieval — ver tests/test_ingestao.py,
  test_consulta_discrimina_planos_com_conteudo_parecido.
"""

from rag_pipeline.models import Chunk, ExtractedDocument


def enrich(document: ExtractedDocument, raw_chunk: dict) -> Chunk:
    raise NotImplementedError
