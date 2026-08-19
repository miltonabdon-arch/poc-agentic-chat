"""Testes de ingestao - ver docs/INGESTAO.md, secao 8."""

from pathlib import Path

from rag_pipeline.chunker import chunk_by_markdown_header
from rag_pipeline.extractor import extract_from_file
from rag_pipeline.metadata_enricher import enrich
from rag_pipeline.query_api import query
from rag_pipeline.vectorizer import get_client, vectorize_and_store

CATALOGO_DIR = Path(__file__).parent.parent / "data" / "catalogo"


def test_documento_com_todas_secoes_gera_chunks_esperados():
    document = extract_from_file(CATALOGO_DIR / "turbo-40gb.md")
    chunks = chunk_by_markdown_header(document)
    sections = {c["section"] for c in chunks}
    assert sections == {"Franquia", "Fidelidade", "Multa de cancelamento", "Elegibilidade"}


def test_documento_sem_secao_opcional_nao_quebra(tmp_path):
    doc_path = tmp_path / "minimo.md"
    doc_path.write_text(
        "---\nplano_id: teste\nnome: Teste\ncategoria: controle\nvigencia_inicio: 2026-01-01\n---\n\n"
        "# Teste\n\n## Franquia\n10GB.\n"
    )
    document = extract_from_file(doc_path)
    chunks = chunk_by_markdown_header(document)
    assert len(chunks) == 1
    assert chunks[0]["section"] == "Franquia"


def test_reingerir_mesmo_documento_nao_duplica(tmp_path):
    client = get_client(str(tmp_path / "chroma_test"))
    document = extract_from_file(CATALOGO_DIR / "turbo-40gb.md")
    chunks = chunk_by_markdown_header(document)

    for raw_chunk in chunks:
        chunk = enrich(document, raw_chunk)
        vectorize_and_store(client, chunk, "test_collection")
        vectorize_and_store(client, chunk, "test_collection")  # reingestao

    from rag_pipeline.vectorizer import get_collection
    collection = get_collection(client, "test_collection")
    assert collection.count() == len(chunks)


def test_consulta_termo_presente_retorna_found_true(tmp_path):
    client = get_client(str(tmp_path / "chroma_test"))
    document = extract_from_file(CATALOGO_DIR / "turbo-40gb.md")
    for raw_chunk in chunk_by_markdown_header(document):
        chunk = enrich(document, raw_chunk)
        vectorize_and_store(client, chunk, "test_collection")

    result = query(client, "franquia do plano turbo 40gb", collection_name="test_collection")
    assert result.found is True
    assert result.source_document_id == "turbo-40gb"


def test_consulta_termo_ausente_retorna_found_false(tmp_path):
    client = get_client(str(tmp_path / "chroma_test"))
    result = query(client, "algo que nao existe em nenhum lugar", collection_name="collection_vazia")
    assert result.found is False


def test_consulta_discrimina_planos_com_conteudo_parecido(tmp_path):
    """Regressão do achado em docs/INGESTAO.md, seção 4: sem o contextual
    chunk header (nome do plano prefixado no texto vetorizado), perguntas
    sobre um plano específico podiam retornar o chunk de outro plano com
    conteúdo textualmente parecido (ex.: Turbo 40GB vs. Família Essencial,
    ambos citando "40GB")."""
    client = get_client(str(tmp_path / "chroma_test"))
    for filename in ["turbo-40gb.md", "familia-essencial.md", "familia-prime.md"]:
        document = extract_from_file(CATALOGO_DIR / filename)
        for raw_chunk in chunk_by_markdown_header(document):
            chunk = enrich(document, raw_chunk)
            vectorize_and_store(client, chunk, "test_collection")

    result = query(client, "Quais franquias de dados o Plano Turbo 40GB inclui?", collection_name="test_collection")
    assert result.found is True
    assert result.source_document_id == "turbo-40gb"

    result_prime = query(client, "Existe fidelidade no Plano Família Prime?", collection_name="test_collection")
    assert result_prime.found is True
    assert result_prime.source_document_id == "familia-prime"


def test_consulta_fora_do_catalogo_nao_inventa_resposta(tmp_path):
    """Regressão: uma pergunta sobre um plano inexistente não deve 'casar'
    por acidente com o chunk mais próximo (ver calibração do threshold em
    docs/INGESTAO.md, seção 7)."""
    client = get_client(str(tmp_path / "chroma_test"))
    for filename in ["turbo-40gb.md", "controle-50gb.md", "familia-prime.md", "pre-pago-turbo.md"]:
        document = extract_from_file(CATALOGO_DIR / filename)
        for raw_chunk in chunk_by_markdown_header(document):
            chunk = enrich(document, raw_chunk)
            vectorize_and_store(client, chunk, "test_collection")

    result = query(client, "Qual o preço do Plano Estratosférico 500GB?", collection_name="test_collection")
    assert result.found is False
