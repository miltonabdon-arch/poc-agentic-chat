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

import frontmatter

from rag_pipeline.models import ExtractedDocument


class UnsupportedFormatError(Exception):
    pass
    

def extract_from_file(path: Path) -> ExtractedDocument:
    if path.suffix != ".md":
        raise UnsupportedFormatError(f"Unsupported file format: {path.suffix!r}")

    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise UnsupportedFormatError(f"File has no YAML front-matter: {path}")

    post = frontmatter.loads(raw)

    return ExtractedDocument(
        raw_text=post.content,
        metadata=dict(post.metadata),
        source_document_id=path.stem,
    )


