"""Contratos de dados do pipeline RAG — ver docs/INGESTAO.md."""

from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    raw_text: str
    metadata: dict
    source_document_id: str


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_document_id: str
    plano_id: str
    categoria: str
    vigencia_inicio: str
    section: str
    nome_plano: str = ""
    status: str = "active"


@dataclass
class QueryResult:
    found: bool
    chunk_id: str | None
    text: str | None
    source_document_id: str | None
    confidence_score: float
