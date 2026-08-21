"""Testes do judge leve offline (agent/judge.py).

Organização:
  - Seção 1: testes de judge_batch (interface legada, compatibilidade com graph.py)
  - Seção 2: testes de pipeline.evaluate_all (interface JudgePipeline, alinhada ao
      agent_framework — ver L-003). Mesma lógica, contrato assíncrono diferente.
"""

import pytest

from agent.judge import (
    _MIN_RESPONSE_CHARS,
    JudgeFinding,
    JudgeResult,
    judge_batch,
    pipeline,
)
from agent.prompt import not_found_response


def _interaction(
    response,
    source_document_id=None,
    interaction_id="i1",
    question=None,
    expects_source=None,
):
    data = {
        "interaction_id": interaction_id,
        "response": response,
        "source_document_id": source_document_id,
    }
    if question is not None:
        data["question"] = question
    if expects_source is not None:
        data["expects_source"] = expects_source
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


def test_groundedness_ok_rag_miss_genuino_com_expects_source():
    """RAG miss genuíno (mensagem 'não encontrei') não deve ser alucinação
    mesmo com expects_source=True — ver orchestrator/graph.py node_judge.
    """
    result = judge_batch([_interaction(
        not_found_response(),
        source_document_id=None,
        expects_source=True,
    )])
    assert not any("alucinação" in r for r in result[0].reasons)


def test_groundedness_nao_aplica_quando_expects_source_false():
    """Domínios CRM (billing/eligibility/simulation) legitimamente não têm
    source_document_id — expects_source=False deve suprimir o check.
    """
    result = judge_batch([_interaction(
        "Sua fatura deste mês é de R$ 79,90.",
        source_document_id=None,
        expects_source=False,
    )])
    assert not any("alucinação" in r for r in result[0].reasons)


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


def test_fabricated_data_nao_aplica_quando_expects_source_false():
    """Domínio CRM (billing) cita nome/valor reais da API mock sem chunk_id —
    não é dado fabricado, é resposta CRM legítima.
    """
    result = judge_batch([_interaction(
        response="Olá, João Silva! Sua fatura de R$ 79,90 venceu ontem.",
        source_document_id=None,
        expects_source=False,
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


# ===========================================================================
# Seção 2: JudgePipeline / evaluate_all — interface alinhada ao framework
# ===========================================================================
# Testa o mesmo comportamento dos 7 checks via contrato assíncrono.
# Objetivo: garantir que a migração de judge_batch → evaluate_all (L-003)
# não regride nenhum caso de negócio, e que node_judge pode adotar
# evaluate_all sem perda de cobertura.
# ===========================================================================


@pytest.mark.asyncio
async def test_pipeline_retorna_lista_de_judge_results():
    results = await pipeline.evaluate_all(
        question="Quais são os planos da TIM?",
        answer="O TIM Turbo 40GB inclui 40GB de dados.",
        context={"source_document_id": "turbo-40gb"},
    )
    assert isinstance(results, list)
    assert all(isinstance(r, JudgeResult) for r in results)
    assert all(hasattr(r, "name") and hasattr(r, "passed") and hasattr(r, "score") for r in results)


@pytest.mark.asyncio
async def test_pipeline_passa_resposta_com_fonte():
    results = await pipeline.evaluate_all(
        question="Quais gigas o Turbo 40GB tem?",
        answer="O Turbo 40GB inclui 40GB de dados 4G/5G.",
        context={"source_document_id": "turbo-40gb"},
    )
    failed = [r for r in results if not r.passed]
    assert not failed, f"Esperava tudo passando, mas falhou: {[r.name for r in failed]}"


@pytest.mark.asyncio
async def test_pipeline_flagga_groundedness_sem_fonte():
    results = await pipeline.evaluate_all(
        question="Quais gigas o Turbo 40GB tem?",
        answer="O Turbo 40GB inclui 40GB de dados 4G/5G.",
        context={"source_document_id": None, "expects_source": True},
    )
    groundedness = next(r for r in results if r.name == "groundedness")
    assert not groundedness.passed
    assert groundedness.score == 0.0


@pytest.mark.asyncio
async def test_pipeline_nao_flagga_dominios_crm_sem_fonte():
    """expects_source=False: billing/eligibility/simulation não usam RAG."""
    results = await pipeline.evaluate_all(
        question="Qual minha fatura?",
        answer="Sua fatura deste mês é de R$ 79,90.",
        context={"source_document_id": None, "expects_source": False},
    )
    groundedness = next(r for r in results if r.name == "groundedness")
    fabricated = next(r for r in results if r.name == "fabricated_data")
    assert groundedness.passed, "domínio CRM não deve ser flaggado por groundedness"
    assert fabricated.passed, "domínio CRM não deve ser flaggado por fabricated_data"


@pytest.mark.asyncio
async def test_pipeline_flagga_not_found_consistency():
    results = await pipeline.evaluate_all(
        question="Quais gigas o Turbo 40GB tem?",
        answer="Não encontrei essa informação no catálogo.",
        context={"source_document_id": "turbo-40gb"},
    )
    nfc = next(r for r in results if r.name == "not_found_consistency")
    assert not nfc.passed


@pytest.mark.asyncio
async def test_pipeline_judge_result_tem_reason_quando_falha():
    results = await pipeline.evaluate_all(
        question="Quais gigas o Turbo 40GB tem?",
        answer="Não encontrei essa informação no catálogo.",
        context={"source_document_id": "turbo-40gb"},
    )
    failed = [r for r in results if not r.passed]
    assert all(r.reason for r in failed), "todo JudgeResult que falha deve ter reason preenchido"


@pytest.mark.asyncio
async def test_pipeline_cobre_os_7_checks():
    """Garante que evaluate_all retorna exatamente 7 JudgeResults — um por check."""
    results = await pipeline.evaluate_all(
        question="Pergunta qualquer",
        answer="Resposta qualquer sobre planos da TIM.",
        context={"source_document_id": "qualquer-doc"},
    )
    assert len(results) == 7
    nomes = {r.name for r in results}
    esperados = {
        "empty_response", "groundedness", "not_found_consistency",
        "length_anomaly", "unwarranted_deflection", "topic_coherence",
        "fabricated_data",
    }
    assert nomes == esperados
