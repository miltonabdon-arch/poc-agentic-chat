"""Testes do judge offline (agent/judge.py).

Interface pública: evaluate_all(question, answer, context) -> list[JudgeResult]
Contrato de saída: JudgeResult(name, score, passed, reason, metadata)
"""

import pytest

from agent_framework.judges.judge import JudgeResult
from agent.judge import (
    evaluate_all,
    FabricatedDataJudge,
    NotFoundConsistencyJudge,
    TopicCoherenceJudge,
    UnwarrantedDeflectionJudge,
)
from agent.prompt import not_found_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(source_document_id=None, evidence=None):
    return {
        "source_document_id": source_document_id,
        "evidence": evidence or "",
    }


def _find(results: list[JudgeResult], name: str) -> JudgeResult | None:
    return next((r for r in results if r.name == name), None)


# ---------------------------------------------------------------------------
# JudgeResult — contrato de saída
# ---------------------------------------------------------------------------

def test_judge_result_tem_campos_do_framework():
    r = JudgeResult(name="teste", score=1.0, passed=True)
    assert hasattr(r, "name")
    assert hasattr(r, "score")
    assert hasattr(r, "passed")
    assert hasattr(r, "reason")
    assert hasattr(r, "metadata")


# ---------------------------------------------------------------------------
# evaluate_all — interface pública
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_all_retorna_lista_de_judge_results():
    results = await evaluate_all("pergunta", "resposta válida com mais de vinte caracteres", _ctx("fonte"))
    assert isinstance(results, list)
    assert all(isinstance(r, JudgeResult) for r in results)


@pytest.mark.asyncio
async def test_evaluate_all_inclui_judges_do_yaml_e_customizados():
    results = await evaluate_all("pergunta", "resposta", _ctx())
    names = {r.name for r in results}
    assert "groundedness" in names
    assert "response_quality" in names
    assert "not_found_consistency" in names
    assert "topic_coherence" in names


# ---------------------------------------------------------------------------
# GroundednessJudge (via evaluate_all)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groundedness_passa_com_overlap_suficiente():
    evidence = "franquia de dados mensal de quarenta gigabytes"
    results = await evaluate_all(
        "qual a franquia",
        "o plano tem franquia de quarenta gigabytes mensais",
        _ctx("turbo-40gb", evidence),
    )
    r = _find(results, "groundedness")
    assert r is not None and r.passed is True


@pytest.mark.asyncio
async def test_groundedness_falha_sem_overlap():
    results = await evaluate_all(
        "qual a franquia",
        "o tempo está lindo hoje",
        _ctx("turbo-40gb", "franquia de dados mensal de quarenta gigabytes"),
    )
    r = _find(results, "groundedness")
    assert r is not None and r.passed is False


# ---------------------------------------------------------------------------
# ResponseQualityJudge (via evaluate_all)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_response_quality_falha_resposta_curta():
    results = await evaluate_all("pergunta", "ok", _ctx("fonte"))
    r = _find(results, "response_quality")
    assert r is not None and r.passed is False


@pytest.mark.asyncio
async def test_response_quality_passa_resposta_adequada():
    results = await evaluate_all(
        "pergunta",
        "O plano inclui franquia de dados e ligações ilimitadas.",
        _ctx("fonte"),
    )
    r = _find(results, "response_quality")
    assert r is not None and r.passed is True


# ---------------------------------------------------------------------------
# NotFoundConsistencyJudge
# ---------------------------------------------------------------------------

def test_not_found_consistency_falha_quando_tinha_fonte():
    j = NotFoundConsistencyJudge()
    r = j.evaluate("", "Não encontrei essa informação no catálogo.", _ctx("turbo-40gb"))
    assert r.passed is False and "fonte disponível" in r.reason


def test_not_found_consistency_falha_com_resposta_padrao():
    j = NotFoundConsistencyJudge()
    r = j.evaluate("", not_found_response(), _ctx("turbo-40gb"))
    assert r.passed is False


def test_not_found_consistency_passa_sem_fonte():
    j = NotFoundConsistencyJudge()
    r = j.evaluate("", "Não encontrei essa informação.", _ctx(None))
    assert r.passed is True


def test_not_found_consistency_passa_resposta_normal_com_fonte():
    j = NotFoundConsistencyJudge()
    r = j.evaluate("", "O plano tem 40GB de franquia.", _ctx("turbo-40gb"))
    assert r.passed is True


# ---------------------------------------------------------------------------
# UnwarrantedDeflectionJudge
# ---------------------------------------------------------------------------

def test_deflection_falha_quando_tinha_fonte():
    j = UnwarrantedDeflectionJudge()
    r = j.evaluate("", "Consulte um atendente para mais informações.", _ctx("controle-100gb"))
    assert r.passed is False and "atendente" in r.reason


def test_deflection_falha_acesse_site_com_fonte():
    j = UnwarrantedDeflectionJudge()
    r = j.evaluate("", "Acesse o site oficial da TIM.", _ctx("turbo-40gb"))
    assert r.passed is False


def test_deflection_passa_sem_fonte():
    j = UnwarrantedDeflectionJudge()
    r = j.evaluate("", "Consulte um atendente.", _ctx(None))
    assert r.passed is True


def test_deflection_passa_resposta_normal():
    j = UnwarrantedDeflectionJudge()
    r = j.evaluate("", "O Plano Controle 100GB inclui internet ilimitada.", _ctx("controle-100gb"))
    assert r.passed is True


# ---------------------------------------------------------------------------
# TopicCoherenceJudge
# ---------------------------------------------------------------------------

def test_topic_coherence_falha_baixo_overlap():
    j = TopicCoherenceJudge()
    r = j.evaluate(
        "quero cancelar minha conta",
        "sua fatura do mês venceu ontem e está disponível para pagamento",
        _ctx("billing"),
    )
    assert r.passed is False and "overlap" in r.reason


def test_topic_coherence_passa_alto_overlap():
    j = TopicCoherenceJudge()
    r = j.evaluate(
        "quero cancelar meu plano",
        "para cancelar seu plano entre em contato com nossa central de cancelamentos",
        _ctx(None),
    )
    assert r.passed is True


def test_topic_coherence_passa_sem_pergunta():
    j = TopicCoherenceJudge()
    r = j.evaluate("", "qualquer resposta", _ctx())
    assert r.passed is True


# ---------------------------------------------------------------------------
# FabricatedDataJudge
# ---------------------------------------------------------------------------

def test_fabricated_data_falha_nome_proprio_sem_fonte():
    j = FabricatedDataJudge()
    r = j.evaluate("", "Olá, João Silva! Sua fatura está em aberto.", _ctx(None))
    assert r.passed is False and "fabricado" in r.reason


def test_fabricated_data_falha_valor_monetario_sem_fonte():
    j = FabricatedDataJudge()
    r = j.evaluate("", "O valor da sua fatura é R$ 79,90.", _ctx(None))
    assert r.passed is False and "fabricado" in r.reason


def test_fabricated_data_passa_com_fonte():
    j = FabricatedDataJudge()
    r = j.evaluate("", "O Plano Controle 100GB custa R$ 99,90 por mês.", _ctx("controle-100gb"))
    assert r.passed is True
