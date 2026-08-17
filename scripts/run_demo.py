#!/usr/bin/env python3
"""Demo ponta a ponta — 5 perguntas dos CRITERIOS-DE-ACEITE.

Uso: python scripts/run_demo.py
Requer que run_ingestao.py já tenha sido executado para perguntas de catálogo.
"""

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv()

from gateway.channel_gateway import normalize
from orchestrator.graph import run_interaction

PERGUNTAS_DEMO = [
    ("Catálogo",     "Quais franquias de dados o Plano Turbo 40GB inclui?"),
    ("Catálogo",     "Existe fidelidade no Plano Família Prime?"),
    ("Fora catálogo","Qual o preço do Plano Estratosférico 500GB?"),
    ("Cancelamento", "Quero cancelar minha linha."),
    ("PII/masking",  "Meu CPF é 123.456.789-00, qual meu plano atual?"),
]


async def main():
    session_id = str(uuid.uuid4())
    print("\n" + "=" * 60)
    print("  DEMO — Agente de Catálogo TIM")
    print("  framework: agent_platform_oci / LangGraph")
    print("=" * 60)

    for i, (categoria, pergunta) in enumerate(PERGUNTAS_DEMO, 1):
        print(f"\n[{i}/5] [{categoria}]")
        print(f"  Usuário : {pergunta}")
        msg = normalize(pergunta, session_id)
        resposta = await run_interaction(msg)
        print(f"  Agente  : {resposta}")

    print("\n" + "=" * 60)
    print("  Demo concluída.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
