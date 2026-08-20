"""Chainlit UI — cliente HTTP do gateway PoC Agente de Catálogo TIM.

Comunicação exclusivamente via HTTP — sem imports de módulos internos:
  POST /agent/interact  — envia mensagem, recebe resposta final
  GET  /trace           — SSE com eventos em tempo real do pipeline

Montado em /chainlit pelo gateway/app.py via mount_chainlit().
"""

from __future__ import annotations

import asyncio
import json
import os

import chainlit as cl
import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

_AGENT_NODES = {
    "informacao",
    "cancelamento_retencao",
    "ativacao",
    "mudanca_plano",
    "supervisor",
}

_STEP_NODES = {"routing_decision"} | _AGENT_NODES | {"judge"}


def _fmt(event: dict) -> str:
    """JSON indentado do payload do evento, removendo campos internos de roteamento."""
    skip = {"type", "session_id", "canal", "node", "guardrail"}
    data = {k: v for k, v in event.items() if k not in skip and v is not None}
    if event.get("node") == "informacao" and "chunk_id" not in data:
        data["found"] = False
    if not data:
        return "✓"
    return f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"


async def _handle_event(event: dict, original_message: str) -> None:
    """Cria um cl.Step expandível por evento SSE relevante."""
    etype = event.get("type", "")

    if etype == "GRL":
        guardrail = event.get("guardrail", "")
        node_name = f"{guardrail}_guardrails"
        async with cl.Step(name=node_name, type="tool") as step:
            if guardrail == "input":
                step.input = original_message
            step.output = _fmt(event)

    elif etype == "NOC":
        node = event.get("node", "")
        if node in _STEP_NODES:
            async with cl.Step(name=node, type="tool") as step:
                step.output = _fmt(event)


@cl.on_chat_start
async def start() -> None:
    await cl.Message(
        content=(
            "**PoC Agente de Catálogo TIM**\n\n"
            "Faça uma pergunta sobre planos, fatura, cancelamento ou ofertas.\n\n"
            "Cada nó do pipeline aparece como step expansível com o JSON de saída em tempo real."
        ),
        author="Sistema",
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    conversation_id = message.id
    sse_connected = asyncio.Event()

    async def sse_loop() -> None:
        """Conecta a GET /trace e processa eventos SSE desta sessão."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream("GET", f"{GATEWAY_URL}/trace") as r:
                    sse_connected.set()
                    async for line in r.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        if event.get("session_id") != conversation_id:
                            continue
                        await _handle_event(event, message.content)
                        if event.get("type") == "SUMARIO":
                            break
        except Exception:
            sse_connected.set()  # Desbloqueia o fluxo principal mesmo se SSE falhar

    sse_task = asyncio.create_task(sse_loop())

    # Aguarda conexão SSE antes de enviar a mensagem (evita perder o primeiro evento)
    try:
        await asyncio.wait_for(sse_connected.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pass

    response_text = "Sem resposta."
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            r = await client.post(
                f"{GATEWAY_URL}/agent/interact",
                json={"message": message.content, "conversation_id": conversation_id},
            )
            r.raise_for_status()
            response_text = r.json().get("response", "Sem resposta.")
    except Exception as exc:
        response_text = f"Erro ao contatar o gateway: {exc}"

    # Aguarda SSE terminar naturalmente (SUMARIO já deve ter chegado antes do POST retornar).
    # asyncio.shield evita que o timeout cancele o task de fora — httpx/anyio não suporta
    # cancelamento cross-task sem RuntimeError.
    try:
        await asyncio.wait_for(asyncio.shield(sse_task), timeout=15.0)
    except Exception:
        pass  # task continua em background e fecha sozinho com o stream

    await cl.Message(content=response_text).send()
