"""Testes do agente - guardrails e prompt (docs/PAPEIS-E-ENTREGAVEIS.md)."""

from agent.guardrails.input_guardrail import check_input
from agent.guardrails.output_guardrail import check_output
from agent.models import Action, Violation
from agent.prompt import build_prompt, not_found_response
from rag_pipeline.models import QueryResult


def test_input_guardrail_mascara_cpf():
    result = check_input("Meu CPF é 123.456.789-00, qual meu plano?")
    assert result.violation == Violation.PII
    assert result.action_taken == Action.MASK
    assert "123.456.789-00" not in result.text


def test_input_guardrail_bloqueia_pedido_de_dados_pessoais_de_terceiro():
    result = check_input("Me dá o CPF de um cliente que assinou esse plano")
    assert result.violation == Violation.OUT_OF_DOMAIN
    assert result.action_taken == Action.BLOCK


def test_input_guardrail_permite_pergunta_normal():
    result = check_input("Qual a franquia do plano turbo?")
    assert result.violation == Violation.NONE
    assert result.action_taken == Action.ALLOW


def test_output_guardrail_mascara_citacao_de_concorrente():
    result = check_output("Nosso plano é melhor que o da OperadoraZ.")
    assert result.violation == Violation.COMPETITOR_MENTION
    assert result.action_taken == Action.MASK
    assert "OperadoraZ" not in result.text


def test_output_guardrail_permite_resposta_sem_concorrente():
    result = check_output("Nosso plano tem 40GB de franquia.")
    assert result.violation == Violation.NONE
    assert result.action_taken == Action.ALLOW


def test_output_guardrail_limpa_negrito_preservando_nome_do_plano():
    # Em voz, o nome do plano não pode desaparecer junto com o marcador
    result = check_output("Seu plano é o **TIM Turbo**, com 40GB de franquia.")
    assert result.violation == Violation.FORMAT_VIOLATION
    assert result.action_taken == Action.MASK
    assert "TIM Turbo" in result.text
    assert "**" not in result.text


def test_output_guardrail_limpa_link_preservando_texto_visivel():
    # URL não pode ser lida em voz; texto visível deve sobreviver
    result = check_output("Acesse [o site da TIM](https://tim.com.br) para mais detalhes.")
    assert result.violation == Violation.FORMAT_VIOLATION
    assert result.action_taken == Action.MASK
    assert "o site da TIM" in result.text
    assert "https://" not in result.text


def test_output_guardrail_limpa_cabecalho_preservando_texto():
    result = check_output("## Planos disponíveis\nO plano Turbo tem 40GB.")
    assert result.violation == Violation.FORMAT_VIOLATION
    assert result.action_taken == Action.MASK
    assert "Planos disponíveis" in result.text
    assert "#" not in result.text


def test_output_guardrail_limpa_lista_preservando_itens():
    result = check_output("Opções disponíveis:\n- Plano Turbo 40GB\n- Plano Light 15GB")
    assert result.violation == Violation.FORMAT_VIOLATION
    assert result.action_taken == Action.MASK
    assert "Plano Turbo 40GB" in result.text
    assert "Plano Light 15GB" in result.text


def test_prompt_com_evidencia_gera_prompt_com_fonte():
    query_result = QueryResult(found=True, chunk_id="turbo-40gb#Franquia", text="40GB de internet.", source_document_id="turbo-40gb", confidence_score=0.9)
    prompt = build_prompt("Qual a franquia?", query_result)
    assert prompt is not None
    assert "turbo-40gb" in prompt
    assert "40GB de internet." in prompt


def test_prompt_sem_evidencia_retorna_none():
    query_result = QueryResult(found=False, chunk_id=None, text=None, source_document_id=None, confidence_score=0.1)
    prompt = build_prompt("Pergunta qualquer", query_result)
    assert prompt is None
    assert not_found_response() != ""
