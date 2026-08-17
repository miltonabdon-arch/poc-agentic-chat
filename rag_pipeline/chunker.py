"""Chunker por header Markdown - ver docs/INGESTAO.md, secao 3.

TODO (Data Engineer): implementar chunk_by_markdown_header() para
satisfazer os testes de tests/test_ingestao.py.

Contrato: retornar uma lista de {"section": str, "text": str} - um item por
header "## " do documento, com o texto entre um header e o proximo (ou o
fim do documento). Ignorar secoes vazias.
"""

from langchain_text_splitters import MarkdownHeaderTextSplitter

from rag_pipeline.models import ExtractedDocument


def chunk_by_markdown_header(document: ExtractedDocument) -> list[dict]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("##", "section")],
        strip_headers=True,
    )
    docs = splitter.split_text(document.raw_text)
    return [
        {"section": doc.metadata["section"], "text": doc.page_content.strip()}
        for doc in docs
        if "section" in doc.metadata and doc.page_content.strip()
    ]

