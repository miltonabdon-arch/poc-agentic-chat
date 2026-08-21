"""Audit log de atualizações de chunks — rastreabilidade de curadoria.

Persiste cada chamada a update_chunk em um SQLite local, registrando
quem alterou, quando, por qual motivo e qual versão foi gerada.

Uso direto (consulta):
    from rag_pipeline.chunk_curator import get_history
    for entry in get_history("turbo-40gb#Franquia_0"):
        print(entry)
"""

import sqlite3
from datetime import datetime
from pathlib import Path

_DEFAULT_DB = "./chunk_audit.db"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_updates (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id           TEXT    NOT NULL,
            source_document_id TEXT    NOT NULL,
            section            TEXT    NOT NULL,
            edited_by          TEXT    NOT NULL,
            updated_at         TEXT    NOT NULL,
            version            INTEGER NOT NULL,
            reason             TEXT    NOT NULL,
            old_text           TEXT    NOT NULL,
            new_text           TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


def log_update(
    chunk_id: str,
    source_document_id: str,
    section: str,
    edited_by: str,
    version: int,
    reason: str,
    old_text: str,
    new_text: str,
    db_path: str = _DEFAULT_DB,
) -> None:
    """Registra uma atualização de chunk no audit log."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chunk_updates
                (chunk_id, source_document_id, section, edited_by, updated_at, version, reason, old_text, new_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, source_document_id, section, edited_by,
             datetime.now().isoformat(timespec="seconds"), version, reason, old_text, new_text),
        )


def get_history(chunk_id: str, db_path: str = _DEFAULT_DB) -> list[dict]:
    """Retorna o histórico de atualizações de um chunk, do mais recente ao mais antigo."""
    db = Path(db_path)
    if not db.exists():
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM chunk_updates WHERE chunk_id = ? ORDER BY id DESC",
            (chunk_id,),
        ).fetchall()
    return [dict(row) for row in rows]
