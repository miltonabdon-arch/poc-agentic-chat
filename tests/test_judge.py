"""Testes do judge leve offline (agent/judge.py)."""

from agent.judge import (
    _MIN_RESPONSE_CHARS,
    JudgeFinding,
    judge_batch,
)
from agent.prompt import not_found_response


def _interaction(response, source_document_id=None, interaction_id="i1"):
    return {
        "interaction_id": interaction_id,
        "response": response,
        "source_document_id": source_document_id,
    }


# --- check_empty_response ---

def test_empty_response_flagga_response_none():
    result = judge_batch([_interaction(None, source_document_id=None)])
    assert result[0].flagged is True
    assert "vazia" in result[0].reason


def test_empty_response_flagga_string_vazia():
    result = judge_batch([_interaction("", source_document_id="turbo-40gb")])
    assert result[0].flagged is True
    assert "vazia" in result[0].reason


def test_empty_response_flagga_apenas_whitespace():
    result = judge_batch([_interaction("   ", source_document_id="turbo-40gb")])
    assert result[0].flagged is True
    assert "vazia" in result[0].reason


# --- check_groundedness ---

def test_groundedness_flagga_response_sem_fonte():
    result = judge_batch([_interaction("Seu plano tem 40GB.", source_document_id=None)])
    assert result[0].flagged is True
    assert "alucinação" in result[0].reason


def test_groundedness_ok_quando_tem_fonte():
    result = judge_batch([_interaction("Seu plano tem 40GB de franquia mensal.", source_document_id="turbo-40gb")])
    assert result[0].flagged is False


def test_groundedness_nao_aplica_a_response_nulo():
    # Resposta nula é capturada por check_empty_response, não por groundedness
    result = judge_batch([_interaction(None, source_document_id=None)])
    assert result[0].flagged is True
    assert "alucinação" not in result[0].reason
    assert "vazia" in result[0].reason


# --- check_not_found_consistency ---

def test_not_found_consistency_flagga_quando_tinha_fonte():
    result = judge_batch([_interaction("Não encontrei esse plano no catálogo.", source_document_id="turbo-40gb")])
    assert result[0].flagged is True
    assert "fonte disponível" in result[0].reason


def test_not_found_consistency_flagga_com_resposta_padrao():
    # not_found_response() começa com "Não encontrei" — deve ser detectada
    result = judge_batch([_interaction(not_found_response(), source_document_id="turbo-40gb")])
    assert result[0].flagged is True
    assert "fonte disponível" in result[0].reason


def test_not_found_consistency_ok_sem_fonte():
    result = judge_batch([_interaction("Não encontrei esse plano no catálogo.", source_document_id=None)])
    # groundedness pode flaggar, mas não not_found_consistency
    assert "fonte disponível" not in (result[0].reason or "")


def test_not_found_consistency_ok_resposta_normal_com_fonte():
    result = judge_batch([_interaction("Plano com 40GB de franquia mensal.", source_document_id="turbo-40gb")])
    assert result[0].flagged is False


# --- check_length_anomaly ---

def test_length_anomaly_flagga_response_curta():
    curta = "X" * (_MIN_RESPONSE_CHARS - 1)
    result = judge_batch([_interaction(curta, source_document_id="turbo-40gb")])
    assert result[0].flagged is True
    assert "curta" in result[0].reason


def test_length_anomaly_ok_response_no_limite():
    no_limite = "X" * _MIN_RESPONSE_CHARS
    result = judge_batch([_interaction(no_limite, source_document_id="turbo-40gb")])
    assert result[0].flagged is False


# --- judge_batch: contrato geral ---

def test_judge_batch_retorna_um_finding_por_interacao():
    interactions = [
        _interaction("Plano 40GB.", source_document_id="turbo-40gb", interaction_id="i1"),
        _interaction("Plano barato.", source_document_id=None, interaction_id="i2"),
    ]
    results = judge_batch(interactions)
    assert len(results) == 2
    assert all(isinstance(r, JudgeFinding) for r in results)
    assert results[0].interaction_id == "i1"
    assert results[1].interaction_id == "i2"


def test_judge_batch_lista_vazia():
    assert judge_batch([]) == []
