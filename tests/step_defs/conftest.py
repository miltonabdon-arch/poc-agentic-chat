"""Fixtures e steps compartilhados entre todos os cenários BDD.

Responsabilidade: AI Developer Sr (Igor Scaglia)

Dois tipos de conteúdo:
  1. Fixtures de infraestrutura (chroma_bdd_unit, caplog_info)
  2. Steps compartilhados — Given/When/Then usados em múltiplos feature files

Separação @unit / @live_llm:
  @unit     → chroma_bdd_unit (Chroma temp, ingestão real, LLM mockado)
  @live_llm → chroma_data/ existente + Flow CI&T real (LLM_BASE_URL obrigatório)
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, then, when

_CATALOGO_DIR = Path(__file__).parent.parent.parent / "data" / "catalogo"
_CHROMA_DATA_DIR = Path(__file__).parent.parent.parent / "chroma_data"
_NOT_FOUND_FRAGMENT = "Não encontrei essa informação"


# ---------------------------------------------------------------------------
# Fixtures de infraestrutura
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def chroma_bdd_unit(tmp_path_factory):
    """Chroma temporário com catálogo ingerido — compartilhado pela sessão BDD.

    Usa os modelos locais (sentence-transformers) sem chamada de rede.
    A ingestão ocorre uma única vez por sessão (scope=session) para não
    penalizar (~30 s de embedding) cada cenário @unit individualmente.
    """
    from rag_pipeline.chunker import chunk_by_markdown_header
    from rag_pipeline.extractor import extract_from_file
    from rag_pipeline.metadata_enricher import enrich
    from rag_pipeline.vectorizer import get_client, vectorize_and_store

    chroma_dir = tmp_path_factory.mktemp("chroma_bdd")
    client = get_client(str(chroma_dir))

    for md_file in sorted(_CATALOGO_DIR.glob("*.md")):
        documento = extract_from_file(md_file)
        for chunk_raw in chunk_by_markdown_header(documento):
            chunk = enrich(documento, chunk_raw)
            # Usa collection_name padrão "catalogo_poc" — mesmo que
            # query_api.query() usa por default em _run_catalog.
            vectorize_and_store(client, chunk)

    return client


@pytest.fixture(autouse=True)
def caplog_info(caplog):
    """Captura logs INFO em todos os cenários deste diretório.

    O traço TRACE|SUMARIO é emitido em INFO por log_sumario_interacao()
    (orchestrator/tracer.py). Sem este fixture, caplog filtraria em WARNING.
    """
    with caplog.at_level(logging.INFO):
        yield


# ---------------------------------------------------------------------------
# Given — contextos
# ---------------------------------------------------------------------------


@given(parsers.parse('uma mensagem "{texto}"'), target_fixture="mensagem")
def dada_mensagem(texto):
    """Cria um ChannelMessage — contrato de Kirllen (gateway/channel_gateway.py)."""
    from gateway.channel_gateway import normalize

    return normalize(texto, conversation_id=f"bdd-{uuid.uuid4().hex[:8]}")


@given(parsers.parse('um texto de entrada "{texto}"'), target_fixture="texto_entrada")
def dado_texto_entrada(texto):
    """Texto bruto para testes isolados de guardrail, sem ChannelMessage."""
    return texto


@given(parsers.parse('uma resposta do LLM "{texto}"'), target_fixture="resposta_llm")
def dada_resposta_llm(texto):
    """Texto fictício do LLM para testar o guardrail de output em isolamento."""
    return texto


# ---------------------------------------------------------------------------
# When — execução do agente ou dos guardrails
# ---------------------------------------------------------------------------


@when(
    parsers.parse('o agente processa com LLM mockado retornando "{resposta_mock}"'),
    target_fixture="interacao",
)
def quando_processa_unit(mensagem, chroma_bdd_unit, caplog, resposta_mock):
    """Pipeline completo com dois patches:
      - rag_pipeline.vectorizer.get_client → Chroma temporário (fixture de sessão)
      - agent.llm_client.complete          → resposta fixa (sem chamada ao Flow API)

    Guardrails (Gustavo), LangGraph (Igor), tracer (Igor) rodam sem mock.
    """
    from orchestrator.graph import run_interaction

    with patch("rag_pipeline.vectorizer.get_client", return_value=chroma_bdd_unit):
        with patch("agent.llm_client.complete", return_value=resposta_mock):
            resposta = asyncio.run(run_interaction(mensagem))

    return {"resposta": resposta}


@when("o agente processa via Flow CI&T", target_fixture="interacao")
def quando_processa_live_llm(mensagem):
    """Pipeline sem mocks — usa chroma_data/ e Flow CI&T reais.

    Pula o cenário se LLM_BASE_URL não estiver configurado ou se
    chroma_data/ não existir (ingestão prévia obrigatória).
    """
    from orchestrator.graph import run_interaction

    if not os.environ.get("LLM_BASE_URL"):
        pytest.skip("LLM_BASE_URL não configurado — cenários @live_llm requerem Flow CI&T")
    if not _CHROMA_DATA_DIR.exists():
        pytest.skip("chroma_data/ ausente — execute scripts/run_ingestao.py primeiro")

    resposta = asyncio.run(run_interaction(mensagem))
    return {"resposta": resposta}


@when("o guardrail de input processa o texto", target_fixture="guardrail_resultado")
def quando_input_guardrail(texto_entrada):
    """Testa check_input() em isolamento — sem grafo, sem LLM, sem Chroma."""
    from agent.guardrails.input_guardrail import check_input

    return check_input(texto_entrada)


@when("o guardrail de output processa a resposta", target_fixture="guardrail_resultado")
def quando_output_guardrail(resposta_llm):
    """Testa check_output() em isolamento — sem grafo, sem LLM, sem Chroma."""
    from agent.guardrails.output_guardrail import check_output

    return check_output(resposta_llm)


# ---------------------------------------------------------------------------
# Then — asserções sobre resposta do pipeline
# ---------------------------------------------------------------------------


@then(parsers.parse('a resposta contém "{esperado}"'))
def entao_resposta_contem(interacao, esperado):
    resposta = interacao["resposta"]
    assert esperado in resposta, (
        f"Esperado '{esperado}' na resposta, não encontrado.\nResposta: {resposta}"
    )


@then(parsers.parse('a resposta não contém "{nao_esperado}"'))
def entao_resposta_nao_contem(interacao, nao_esperado):
    resposta = interacao["resposta"]
    assert nao_esperado not in resposta, (
        f"'{nao_esperado}' não deveria estar na resposta.\nResposta: {resposta}"
    )


@then("a resposta indica que a informação não foi encontrada")
def entao_nao_encontrado(interacao):
    """§4: sem evidência RAG, o agente usa build_not_found_prompt() + LLM sem inventar.

    Fragmento vem de agent/prompt.py — contrato de Gustavo (test_new_branch).
    """
    resposta = interacao["resposta"]
    assert _NOT_FOUND_FRAGMENT in resposta, (
        f"Esperado fragmento '{_NOT_FOUND_FRAGMENT}' (not_found_response).\n"
        f"Resposta obtida: {resposta}"
    )


@then(parsers.parse('o traço contém chunk_id "{prefixo}"'))
def entao_trace_chunk_id(caplog, prefixo):
    """§3 e §6: chunk_id do documento RAG deve aparecer no TRACE|SUMARIO.

    O sumário é emitido por log_sumario_interacao() (orchestrator/tracer.py).
    """
    sumario_lines = [r.message for r in caplog.records if "SUMARIO" in r.message]
    assert any(prefixo in linha for linha in sumario_lines), (
        f"chunk_id com prefixo '{prefixo}' não encontrado no SUMARIO.\n"
        f"Linhas SUMARIO capturadas: {sumario_lines}"
    )


@then(parsers.parse('o traço SUMARIO contém "{campo}"'))
def entao_trace_sumario_contem(caplog, campo):
    """§6: verifica que um campo aparece no TRACE|SUMARIO."""
    sumario_lines = [r.message for r in caplog.records if "SUMARIO" in r.message]
    assert sumario_lines, "Nenhuma linha TRACE|SUMARIO encontrada nos logs."
    assert any(campo in linha for linha in sumario_lines), (
        f"Campo '{campo}' não encontrado no SUMARIO.\nLinhas: {sumario_lines}"
    )


# ---------------------------------------------------------------------------
# Then — asserções sobre resultados isolados de guardrail
# ---------------------------------------------------------------------------


@then(parsers.parse('a violação registrada é "{violacao}"'))
def entao_violacao_e(guardrail_resultado, violacao):
    assert guardrail_resultado.violation.value == violacao, (
        f"Esperado violation='{violacao}', obtido '{guardrail_resultado.violation.value}'"
    )


@then(parsers.parse('a ação tomada é "{acao}"'))
def entao_acao_e(guardrail_resultado, acao):
    assert guardrail_resultado.action_taken.value == acao, (
        f"Esperado action_taken='{acao}', obtido '{guardrail_resultado.action_taken.value}'"
    )


@then(parsers.parse('o texto sanitizado não contém "{texto}"'))
def entao_sanitizado_nao_contem(guardrail_resultado, texto):
    assert texto not in guardrail_resultado.text, (
        f"'{texto}' não deveria estar no texto sanitizado.\nTexto: {guardrail_resultado.text}"
    )


@then(parsers.parse('o texto sanitizado contém "{texto}"'))
def entao_sanitizado_contem(guardrail_resultado, texto):
    assert texto in guardrail_resultado.text, (
        f"Esperado '{texto}' no texto sanitizado.\nTexto: {guardrail_resultado.text}"
    )


@then(parsers.parse('o texto resultante não contém "{texto}"'))
def entao_resultado_nao_contem(guardrail_resultado, texto):
    """Para resultados de guardrail de output (texto resultante ≠ texto sanitizado)."""
    assert texto not in guardrail_resultado.text, (
        f"'{texto}' não deveria estar no resultado do guardrail.\nTexto: {guardrail_resultado.text}"
    )


@then(parsers.parse('o texto resultante contém "{texto}"'))
def entao_resultado_contem(guardrail_resultado, texto):
    assert texto in guardrail_resultado.text, (
        f"Esperado '{texto}' no resultado do guardrail.\nTexto: {guardrail_resultado.text}"
    )
