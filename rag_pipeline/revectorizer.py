"""Atualiza o embedding e o texto de um chunk existente.

    Busca os metadados atuais do chunk para preservá-los, incrementa
    `version` e registra `updated_at`. Levanta ChunkNotFoundError se
    o chunk_id não existir na collection.
"""

from datetime import date

import chromadb

from rag_pipeline.chunk_curator import log_update
from rag_pipeline.vectorizer import get_collection

_DEFAULT_COLLECTION = "catalogo_poc"


class ChunkNotFoundError(Exception):
    pass


def update_chunk(
    client: chromadb.ClientAPI,
    chunk_id: str,
    new_text: str,
    edited_by: str,
    reason: str,
    collection_name: str = _DEFAULT_COLLECTION,
) -> None:
    collection = get_collection(client, collection_name)

    existing = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        raise ChunkNotFoundError(f"chunk_id não encontrado: {chunk_id!r}")

    old_text = existing["documents"][0]
    metadata = existing["metadatas"][0]
    metadata["version"] = int(metadata.get("version", 1)) + 1
    metadata["updated_at"] = date.today().isoformat()

    full_text = f"{metadata['section']} {metadata['nome_plano']} (ID: {metadata['plano_id']}): {new_text}"

    collection.update(
        ids=[chunk_id],
        documents=[full_text],
        metadatas=[metadata],
    )

    log_update(
        chunk_id=chunk_id,
        source_document_id=metadata["source_document_id"],
        section=metadata["section"],
        edited_by=edited_by,
        version=metadata["version"],
        reason=reason,
        old_text=old_text,
        new_text=full_text,
    )
