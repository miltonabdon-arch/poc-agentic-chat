"""Chunker por header Markdown - ver docs/INGESTAO.md, secao 3.

TODO (Data Engineer): implementar chunk_by_markdown_header() para
satisfazer os testes de tests/test_ingestao.py.

Contrato: retornar uma lista de {"section": str, "text": str} - um item por
header "## " do documento, com o texto entre um header e o proximo (ou o
fim do documento). Ignorar secoes vazias.
"""

from rag_pipeline.models import ExtractedDocument


def chunk_by_markdown_header(document: ExtractedDocument) -> list[dict]:
    raise NotImplementedError
