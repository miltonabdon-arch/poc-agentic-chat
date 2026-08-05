#!/usr/bin/env python3
"""CLI de ingestao - ver docs/INGESTAO.md, secao 6.

Uso: python scripts/run_ingestao.py --input data/catalogo/ --collection catalogo_poc
"""

import argparse
import time
from pathlib import Path

from rag_pipeline.chunker import chunk_by_markdown_header
from rag_pipeline.extractor import extract_from_file
from rag_pipeline.metadata_enricher import enrich
from rag_pipeline.vectorizer import get_client, vectorize_and_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/catalogo/")
    parser.add_argument("--collection", default="catalogo_poc")
    parser.add_argument("--persist-path", default="./chroma_data")
    args = parser.parse_args()

    start = time.time()
    client = get_client(args.persist_path)

    documents_processed = 0
    chunks_processed = 0

    for path in sorted(Path(args.input).glob("*.md")):
        document = extract_from_file(path)
        raw_chunks = chunk_by_markdown_header(document)
        for raw_chunk in raw_chunks:
            chunk = enrich(document, raw_chunk)
            vectorize_and_store(client, chunk, args.collection)
            chunks_processed += 1
        documents_processed += 1

    elapsed = time.time() - start
    print(f"Ingestão concluída: {documents_processed} documentos, {chunks_processed} chunks, {elapsed:.1f}s")
    print(f"Collection: {args.collection} (Chroma local, {args.persist_path})")


if __name__ == "__main__":
    main()
