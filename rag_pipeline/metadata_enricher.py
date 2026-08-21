"""Enriquecedor de metadados - ver docs/INGESTAO.md, secao 4.

TODO (Data Engineer): implementar enrich() para satisfazer os testes de
tests/test_ingestao.py.

Contrato (ver Chunk em rag_pipeline/models.py):
- chunk_id = f"{document.source_document_id}#{section}"
- plano_id, categoria, vigencia_inicio vêm de document.metadata
- nome_plano vem de document.metadata["nome"]
- Atenção ao risco descrito em docs/INGESTAO.md, seção 4: se o texto
  vetorizado (Chunk.text) não deixar claro a qual plano ele pertence,
  perguntas sobre planos com conteúdo parecido podem se confundir no
  retrieval — ver tests/test_ingestao.py,
  test_consulta_discrimina_planos_com_conteudo_parecido.
"""

from rag_pipeline.models import Chunk, ExtractedDocument


def enrich(document: ExtractedDocument, raw_chunk: dict) -> Chunk:

    return Chunk(
        chunk_id=f"{document.source_document_id}#{raw_chunk['section']}_{raw_chunk['window_index']}",
        text=f"{raw_chunk['section']} {document.metadata['nome']} (ID: {document.metadata['plano_id']}): {raw_chunk['text']}",
        source_document_id=document.source_document_id,
        plano_id=document.metadata["plano_id"],
        categoria=document.metadata["categoria"],
        vigencia_inicio=document.metadata["vigencia_inicio"],
        section=raw_chunk["section"],
        nome_plano=document.metadata["nome"],
        status="active"
      )
