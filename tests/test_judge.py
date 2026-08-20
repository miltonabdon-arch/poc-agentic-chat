"""Testes do judge leve offline (agent/judge.py)."""

from agent.judge import (
    _MIN_RESPONSE_CHARS,
    _MIN_TOPIC_OVERLAP,
    JudgeFinding,
    judge_batch,
)
from agent.prompt import not_found_response


def _interaction(
    response,
    source_document_id=None,
    interaction_id="i1",
    question=None,
):
    data = {
        "interaction_id": interaction_id,
        "response": response,
        "source_document_id": source_document_id,
    }
    if question is not None:
        data["question"] = question
    return data


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


# --- check_unwarranted_deflection ---

def test_deflection_flagga_quando_tinha_fonte():
    result = judge_batch([_interaction(
        "Consulte um atendente para mais informações.",
        source_document_id="controle-100gb",
    )])
    assert result[0].flagged is True
    assert "atendente" in result[0].reason


def test_deflection_flagga_acesse_site_com_fonte():
    result = judge_batch([_interaction(
        "Acesse o site oficial da TIM para mais detalhes.",
        source_document_id="turbo-40gb",
    )])
    assert result[0].flagged is True
    assert "atendente" in result[0].reason


def test_deflection_ok_sem_fonte():
    result = judge_batch([_interaction(
        "Consulte um atendente para mais informações.",
        source_document_id=None,
    )])
    assert "atendente" not in (result[0].reason or "")


def test_deflection_ok_resposta_normal_com_fonte():
    result = judge_batch([_interaction(
        "O Plano Controle 100GB inclui internet e ligações ilimitadas.",
        source_document_id="controle-100gb",
    )])
    assert result[0].flagged is False


# --- check_topic_coherence ---

def test_topic_coherence_flagga_baixo_overlap():
    result = judge_batch([_interaction(
        question="quero cancelar minha conta",
        response="Sua fatura do mês de agosto venceu no dia dez e está disponível para pagamento.",
        source_document_id="billing",
    )])
    assert result[0].flagged is True
    assert "overlap" in result[0].reasons[-1] or any("overlap" in r for r in result[0].reasons)


def test_topic_coherence_ok_alto_overlap():
    result = judge_batch([_interaction(
        question="quero cancelar meu plano",
        response="Para cancelar seu plano entre em contato com nossa central de cancelamentos.",
        source_document_id=None,
    )])
    assert not any("overlap" in r for r in result[0].reasons)


def test_topic_coherence_ignorado_sem_question():
    result = judge_batch([_interaction(
        response="Sua fatura está disponível para pagamento.",
        source_document_id="billing",
    )])
    assert not any("overlap" in r for r in result[0].reasons)


# --- check_fabricated_data ---

def test_fabricated_data_flagga_nome_proprio_sem_fonte():
    result = judge_batch([_interaction(
        response="Olá, João Silva! Sua fatura está em aberto.",
        source_document_id=None,
    )])
    assert result[0].flagged is True
    assert any("fabricado" in r for r in result[0].reasons)


def test_fabricated_data_flagga_valor_monetario_sem_fonte():
    result = judge_batch([_interaction(
        response="O valor da sua fatura é R$ 79,90.",
        source_document_id=None,
    )])
    assert result[0].flagged is True
    assert any("fabricado" in r for r in result[0].reasons)


def test_fabricated_data_ok_com_fonte():
    result = judge_batch([_interaction(
        response="O Plano Controle 100GB custa R$ 99,90 por mês.",
        source_document_id="controle-100gb",
    )])
    assert not any("fabricado" in r for r in result[0].reasons)


# --- acumula todos os reasons ---

def test_judge_acumula_multiplos_problemas():
    result = judge_batch([_interaction(
        question="cancelar conta",
        response="Sua fatura de R$ 79,90 venceu ontem.",
        source_document_id=None,
    )])
    assert result[0].flagged is True
    assert len(result[0].reasons) >= 2


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
