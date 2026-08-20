"""Testes do agente - guardrails e prompt (docs/PAPEIS-E-ENTREGAVEIS.md)."""

from agent.guardrails.input_guardrail import check_input
from agent.guardrails.output_guardrail import check_output
from agent.judge import judge_batch
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


def test_build_crm_prompt_inclui_intent_e_dados():
    from agent.prompt import build_crm_prompt
    dados = {"nome": "João", "mensalidade": 79.90}
    prompt = build_crm_prompt("Qual minha fatura?", "billing", dados)
    assert "billing" in prompt
    assert "João" in prompt
    assert "79.9" in prompt
    assert "Qual minha fatura?" in prompt


def test_build_crm_prompt_dados_aninhados():
    from agent.prompt import build_crm_prompt
    dados = {"cliente": {"nome": "Ana"}, "elegibilidade": {"pode_trocar": True}}
    prompt = build_crm_prompt("Posso trocar de plano?", "eligibility", dados)
    assert "eligibility" in prompt
    assert "pode_trocar" in prompt
    assert "Posso trocar de plano?" in prompt


def test_build_supervisor_prompt_inclui_dominios():
    from agent.prompt import build_supervisor_prompt
    prompt = build_supervisor_prompt("olá")
    assert "Planos e catálogo" in prompt or "cancelamento" in prompt.lower()
    assert "olá" in prompt


def test_build_not_found_prompt_inclui_instrucoes():
    from agent.prompt import build_not_found_prompt
    prompt = build_not_found_prompt("Qual o preço do plano X99?")
    assert "Qual o preço do plano X99?" in prompt
    assert "não" in prompt.lower() or "pré-pago" in prompt.lower()


def test_judge_nao_flagga_rota_sem_fonte():
    items = [
        {
            "interaction_id": "test-1",
            "response": "Sua fatura deste mês é de R$ 79,90.",
            "source_document_id": None,
            "expects_source": False,
        }
    ]
    findings = judge_batch(items)
    assert len(findings) == 1
    assert not findings[0].flagged, f"Esperava não flaggado, mas reason={findings[0].reason}"
