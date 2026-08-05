"""Extrator de texto — ver docs/INGESTAO.md, secao 2.

Separa front-matter (YAML) do corpo (Markdown) de um documento sintetico
do catalogo. Sem OCR: os documentos de entrada ja sao Markdown puro.

TODO (Data Engineer): implementar extract_from_file() para satisfazer os
testes de tests/test_ingestao.py.

Contrato (ver ExtractedDocument em rag_pipeline/models.py):
- Ler o arquivo .md em UTF-8
- Separar front-matter YAML (delimitado por "---") do corpo Markdown
- Levantar UnsupportedFormatError se a extensao != ".md" ou se o documento
  nao comecar com front-matter YAML
- source_document_id = nome do arquivo sem extensao (path.stem)
"""

from pathlib import Path

from rag_pipeline.models import ExtractedDocument


class UnsupportedFormatError(Exception):
    pass


def extract_from_file(path: Path) -> ExtractedDocument:
    raise NotImplementedError
