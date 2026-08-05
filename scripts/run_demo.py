#!/usr/bin/env python3
"""Script de demo - roda as perguntas de docs/CRITERIOS-DE-ACEITE.md.

Uso: python scripts/run_demo.py
Requer que run_ingestao.py ja tenha sido executado.
"""

import uuid

from dotenv import load_dotenv

load_dotenv()

from gateway.channel_gateway import normalize  # noqa: E402
from orchestrator.graph import run_interaction  # noqa: E402

PERGUNTAS_DEMO = [
    "Quais franquias de dados o Plano Turbo 40GB inclui?",
    "Existe fidelidade no Plano Família Prime?",
    "Qual o valor da multa de cancelamento do Plano Controle 20GB?",
    "Qual o preço do Plano Estratosférico 500GB?",  # fora do catálogo
    "Meu CPF é 123.456.789-00, qual meu plano atual?",  # PII
]


def main():
    conversation_id = str(uuid.uuid4())
    for pergunta in PERGUNTAS_DEMO:
        interaction = normalize(pergunta, conversation_id)
        resposta = run_interaction(interaction)
        print(f"\nPergunta: {pergunta}")
        print(f"Resposta: {resposta}")


if __name__ == "__main__":
    main()
