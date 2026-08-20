"""Chainlit UI — cliente HTTP do gateway PoC Agente de Catálogo TIM.

Comunicação exclusivamente via HTTP — sem imports de módulos internos:
  POST /agent/interact  — envia mensagem, recebe resposta final
  GET  /trace           — SSE com eventos em tempo real do pipeline

Montado em /chainlit pelo gateway/app.py via mount_chainlit().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

import chainlit as cl
import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

logger = logging.getLogger(__name__)

# Whitelist dos nós do grafo que geram cl.Step no handler NOC genérico.
# routing_decision tem tratamento especial (SUG-03) e cai fora desse bloco,
# mas precisa estar aqui para não ser silenciado pela guard `if node in _STEP_NODES`.
# Nós cujo NOC tem conteúdo exibível. routing_decision tem tratamento especial
# (SUG-03) antes deste check — não precisa estar aqui. Todos os outros nós
# chegam sem campos úteis após _fmt() (output = "✓"), informação já coberta
# por RAG/MOCK/LLM/STATE. Set vazio = todos os NOC genéricos são silenciados.
_STEP_NODES: set[str] = set()

# Ícones por tipo de evento de especialidade
_TYPE_ICON = {
    "FLOW": "⚙️",
    "LLM": "🤖",
    "RAG": "🔍",
    "MOCK": "🎭",
    "JUDGE": "⚖️",
    "GRL": "🛡️",
    "NOC": "✅",
    "GRAPH": "🗺️",
    "ORCH": "🏁",
    "STATE": "📊",
}

# SUG-01: mapeamento componente FLOW → fase do TaskList
_FLOW_TO_TASK = {
    "node.input_guardrails": "guardrails_in",
    "node.routing_decision": "roteamento",
    "node.catalog_agent": "processamento",
    "node.billing": "processamento",
    "node.handoff_cancellation": "processamento",
    "node.handoff_deals": "processamento",
    "node.eligibility": "processamento",
    "node.simulation": "processamento",
    "node.supervisor": "processamento",
    "node.output_guardrails": "guardrails_out",
    "node.judge": "avaliacao",
}

# SUG-04: mapeamento nó do STATE → fase do TaskList
_STATE_TO_TASK = {
    "input_guardrails": "guardrails_in",
    "routing_decision": "roteamento",
    "catalog_agent": "processamento",
    "billing": "processamento",
    "handoff_cancellation": "processamento",
    "handoff_deals": "processamento",
    "eligibility": "processamento",
    "simulation": "processamento",
    "supervisor": "processamento",
    "output_guardrails": "guardrails_out",
    "judge": "avaliacao",
}


def _fmt(event: dict) -> str:
    """JSON indentado do payload do evento, removendo campos de roteamento interno.

    Campos omitidos (já exibidos em outras partes da UI ou não relevantes ao usuário):
      type, session_id, canal, node, guardrail, subtype, component, owner →
          metadados de roteamento do broadcaster
      initial_state, final_state, delta →
          exibidos separadamente via _fmt_state() nos handlers GRAPH/ORCH/STATE
    """
    skip = {
        "type", "session_id", "canal", "node", "guardrail",
        "subtype", "component", "owner",
        "initial_state", "final_state", "delta",
    }
    data = {k: v for k, v in event.items() if k not in skip and v is not None}
    if event.get("node") == "catalog_agent" and "chunk_id" not in data:
        data["found"] = False
    if not data:
        return "✓"
    return f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"


def _fmt_state(state: dict) -> str:
    """Formata snapshot do GraphState como markdown legível."""
    if not state:
        return "(estado vazio)"
    lines = []
    for k, v in state.items():
        if k == "guardrail_decisions" and isinstance(v, list):
            if v:
                for i, grl in enumerate(v):
                    lines.append(
                        f"- `guardrail[{i}]`: type=`{grl.get('type','?')}` "
                        f"violation=`{grl.get('violation','?')}` "
                        f"blocked=`{grl.get('blocked','?')}`"
                    )
            else:
                lines.append("- `guardrail_decisions`: `[]`")
        else:
            v_str = str(v) if v is not None else "null"
            if len(v_str) > 100:
                v_str = v_str[:100] + "…"
            lines.append(f"- `{k}`: `{v_str}`")
    return "\n".join(lines)


async def _handle_event(
    event: dict,
    original_message: str,
    pending_steps: dict[str, cl.Step],
    task_list: cl.TaskList,
    tasks: dict[str, cl.Task],
) -> None:
    """Cria / atualiza cl.Step ou cl.Message por tipo de evento SSE.

    Cada tipo de evento produz um elemento diferente na UI Chainlit:
      FLOW  → sub-componentes (rag.query, llm.complete, mock.*): step aberto no ENTER,
              fechado no EXIT com latência. Nós do grafo (node.*): só atualiza TaskList,
              sem step — a informação de nó já é coberta por GRL/NOC/STATE.
      STATE → step compacto com campos do GraphState que mudaram após o nó.
              Suprimido para routing_decision (NOC já exibiu) e output_guardrails (ORCH exibirá).
      GRL   → step com resultado do guardrail. Suprimido quando blocked=False e violation=none
              (guardrail silencioso não agrega informação). Ativo apenas em bloqueio/violação.
      NOC   → step de nó concluído; routing_decision tem formato especial (SUG-03).
      LLM   → step com prompt e resposta do modelo.
      RAG   → step com chunk encontrado (ou miss).
      MOCK  → step com serviço e HTTP status.
      JUDGE → step com avaliação offline de qualidade.
      GRAPH → step com topologia compilada (estado inicial omitido: sempre vazio).
      ORCH  → cl.Message com estado final e resultado do pipeline (SUG-02).
    """
    etype = event.get("type", "")
    icon = _TYPE_ICON.get(etype, "")

    if etype == "keepalive":
        # O broadcaster emite keepalives periódicos para manter a conexão SSE viva
        return

    # ------------------------------------------------------------------
    # FLOW — abre step no ENTER, fecha com resultado no EXIT
    # ------------------------------------------------------------------
    if etype == "FLOW":
        subtype = event.get("subtype", "")
        component = event.get("component", "")
        # Chave única por sessão+componente para parear ENTER → EXIT corretamente
        # em conversas concorrentes (cada session_id tem seu próprio espaço)
        step_key = f"{event.get('session_id')}:{component}"
        label = f"{icon} {component}"

        if subtype == "ENTER":
            # SUG-01: avança fase para RUNNING quando o nó começa
            task_key = _FLOW_TO_TASK.get(component)
            if task_key and task_key in tasks:
                tasks[task_key].status = cl.TaskStatus.RUNNING
                await task_list.send()
            # Nós do grafo (node.*): sem step na UI — informação já coberta por GRL/NOC/STATE
            if component.startswith("node."):
                return
            step = cl.Step(name=label, type="tool")
            await step.__aenter__()
            # Guarda referência para fechar no EXIT correspondente
            pending_steps[step_key] = step

        elif subtype == "EXIT":
            # node.* não insere em pending_steps; pop retorna None → no-op seguro
            step = pending_steps.pop(step_key, None)
            if step is not None:
                status = event.get("status", "OK")
                step.output = _fmt(event)
                # Marca visualmente com ❌ quando o componente retornou ERROR
                if status == "ERROR":
                    step.name = f"❌ {label}"
                await step.__aexit__(None, None, None)

        return

    # ------------------------------------------------------------------
    # STATE — snapshot do GraphState após cada nó (SUG-04)
    # ------------------------------------------------------------------
    if etype == "STATE":
        node = event.get("node", "")
        delta = event.get("delta", {})
        # SUG-01: avança fase para DONE após o nó concluir
        task_key = _STATE_TO_TASK.get(node)
        if task_key and task_key in tasks:
            tasks[task_key].status = cl.TaskStatus.DONE
            await task_list.send()
        # routing_decision: NOC já exibiu rota+intenção em formato legível
        # output_guardrails: ORCH exibirá final_answer; não repetir aqui
        if node in ("routing_decision", "output_guardrails"):
            return
        # Exibe delta do estado como step compacto
        if delta:
            lines = []
            for k, v in delta.items():
                if k == "guardrail_decisions" and isinstance(v, list):
                    for grl in v:
                        lines.append(
                            f"`guardrail`: type=`{grl.get('type','?')}` "
                            f"violation=`{grl.get('violation','?')}` "
                            f"blocked=`{grl.get('blocked','?')}`"
                        )
                else:
                    v_str = str(v)
                    if len(v_str) > 100:
                        v_str = v_str[:100] + "…"
                    lines.append(f"`{k}` → `{v_str}`")
            async with cl.Step(name=f"📊 Δ {node}", type="tool") as step:
                step.output = "\n".join(lines)
        return

    # ------------------------------------------------------------------
    # GRL — guardrail
    # ------------------------------------------------------------------
    if etype == "GRL":
        guardrail = event.get("guardrail", "")
        blocked = event.get("blocked", False)
        violation = (event.get("violation") or "none").lower()
        # Guardrail silencioso (sem bloqueio, sem violação): não poluir a UI
        # A passagem limpa já é evidenciada pelo STATE delta do mesmo nó
        if not blocked and violation in ("none", ""):
            return
        node_name = f"{icon} {guardrail}_guardrails"
        if blocked:
            node_name = f"🚫 {guardrail}_guardrails [BLOQUEADO]"
        async with cl.Step(name=node_name, type="tool") as step:
            if guardrail == "input":
                step.input = original_message
            step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # NOC — nó completo (SUG-03: routing_decision legível)
    # ------------------------------------------------------------------
    if etype == "NOC":
        node = event.get("node", "")
        if node == "routing_decision":
            # SUG-03: exibe rota + intenção em formato humano em vez de JSON raw
            intent = event.get("intent", "?")
            agent = event.get("agent", "?")
            sanitized = event.get("sanitized_input", "")
            async with cl.Step(
                name=f"✅ rota → `{agent}` · intenção: `{intent}`",
                type="tool",
            ) as step:
                step.input = sanitized
                step.output = "Roteamento via `EnterpriseRouter` (palavras-chave, sem LLM)"
            return
        # Nós não listados em _STEP_NODES são silenciados (ex.: sub-componentes internos)
        if node in _STEP_NODES:
            async with cl.Step(name=f"{icon} {node}", type="tool") as step:
                step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # LLM — chamada ao modelo de linguagem
    # ------------------------------------------------------------------
    if etype == "LLM":
        model = event.get("model", "?")
        async with cl.Step(name=f"{icon} LLM ({model})", type="llm") as step:
            step.input = event.get("prompt", "")
            step.output = event.get("response", _fmt(event))
        return

    # ------------------------------------------------------------------
    # RAG — busca no catálogo vetorial
    # ------------------------------------------------------------------
    if etype == "RAG":
        found = event.get("found", False)
        chunk_id = event.get("chunk_id")
        label = f"{icon} RAG {'✓ ' + str(chunk_id) if found else '✗ não encontrado'}"
        async with cl.Step(name=label, type="retrieval") as step:
            step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # MOCK — chamada a serviço mockado
    # ------------------------------------------------------------------
    if etype == "MOCK":
        service = event.get("service", "?")
        http_status = event.get("http_status", "?")
        async with cl.Step(name=f"{icon} MOCK:{service} [{http_status}]", type="tool") as step:
            step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # JUDGE — avaliação offline de qualidade
    # ------------------------------------------------------------------
    if etype == "JUDGE":
        status = event.get("status", "OK")
        label = f"{icon} JUDGE [{'OK' if status == 'OK' else '⚠️ ERRO'}]"
        async with cl.Step(name=label, type="tool") as step:
            step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # GRAPH — topologia compilada
    # ------------------------------------------------------------------
    if etype == "GRAPH":
        nodes = event.get("graph_nodes", "?")
        entry = event.get("entry_point", "?")
        # Estado inicial omitido: sempre vazio no começo da execução, não agrega informação
        async with cl.Step(name=f"{icon} GRAPH [{nodes} nós · entrada: {entry}]", type="tool") as step:
            step.output = _fmt(event)
        return

    # ------------------------------------------------------------------
    # ORCH — resultado como Message com estado final (SUG-02)
    # ------------------------------------------------------------------
    if etype == "ORCH":
        route = event.get("route", "?")
        latencia = event.get("latencia_ms", "?")
        blocked = event.get("blocked", False)
        final = event.get("final_state", {})

        # SUG-01: finaliza todas as fases pendentes
        for task in tasks.values():
            if task.status != cl.TaskStatus.DONE:
                task.status = cl.TaskStatus.DONE
        task_list.status = "Concluído ✓"
        await task_list.send()

        lines = [f"**🏁 Pipeline concluído** — `{route}` · {latencia}ms"]
        if blocked:
            lines.append("\n⚠️ **Resposta bloqueada** pelo guardrail de entrada.")
        if final:
            lines.append("\n**Estado final do grafo:**")
            lines.append(_fmt_state(final))

        await cl.Message(
            content="\n".join(lines),
            author="Orquestrador",
        ).send()
        return


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("conversation_id", str(uuid.uuid4()))
    await cl.Message(
        content=(
            "**PoC Agente de Catálogo TIM**\n\n"
            "Faça uma pergunta sobre planos, fatura, cancelamento ou ofertas.\n\n"
            "Cada componente do pipeline aparece como step expansível em tempo real,\n"
            "com o estado do grafo evoluindo a cada passo."
        ),
        author="Sistema",
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    conversation_id = cl.user_session.get("conversation_id") or message.id
    # sse_connected sinaliza quando a conexão SSE foi estabelecida,
    # permitindo que o POST ao gateway só seja enviado depois que o
    # broadcaster já tem um consumidor — evita perder eventos iniciais (IC/GRAPH)
    sse_connected = asyncio.Event()
    # Armazena cl.Step abertos pelo FLOW ENTER, fechados pelo FLOW EXIT
    pending_steps: dict[str, cl.Step] = {}

    # SUG-01: TaskList com as 5 fases do pipeline
    task_list = cl.TaskList()
    task_list.status = "Processando..."
    tasks: dict[str, cl.Task] = {
        "guardrails_in": cl.Task(title="Guardrails de entrada", status=cl.TaskStatus.READY),
        "roteamento":    cl.Task(title="Roteamento de intenção", status=cl.TaskStatus.READY),
        "processamento": cl.Task(title="Processamento", status=cl.TaskStatus.READY),
        "guardrails_out": cl.Task(title="Guardrails de saída", status=cl.TaskStatus.READY),
        "avaliacao":     cl.Task(title="Avaliação de qualidade", status=cl.TaskStatus.READY),
    }
    for task in tasks.values():
        await task_list.add_task(task)
    await task_list.send()

    async def sse_loop() -> None:
        # Closure captura: conversation_id, message.content, pending_steps, task_list, tasks
        # — todas as variáveis de estado desta invocação de on_message
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream("GET", f"{GATEWAY_URL}/trace") as r:
                    # Sinaliza antes de iterar: garante que o POST ao gateway
                    # só é feito quando já há um consumidor SSE ativo
                    sse_connected.set()
                    async for line in r.aiter_lines():
                        if not line.startswith("data: "):
                            # Linhas do protocolo SSE sem payload (ex.: "event:", "id:", "")
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        # Filtra eventos de outras conversas no mesmo stream SSE broadcast
                        if event.get("session_id") != conversation_id:
                            continue
                        await _handle_event(event, message.content, pending_steps, task_list, tasks)
                        # ORCH é o último evento do pipeline — encerra o loop sem esperar timeout
                        if event.get("type") == "ORCH":
                            break
        except Exception as exc:
            # G10: falha de SSE não deve ser silenciosa — registra para diagnóstico
            logger.warning("[CHAINLIT] SSE connect falhou: %s", exc, exc_info=True)
            # Libera o wait abaixo mesmo em erro para não bloquear o POST ao gateway
            sse_connected.set()

    sse_task = asyncio.create_task(sse_loop())

    try:
        await asyncio.wait_for(sse_connected.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("[CHAINLIT] SSE connect timeout após 10s")

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
        logger.warning("[CHAINLIT] POST /agent/interact falhou: %s", exc)
        response_text = f"Erro ao contatar o gateway: {exc}"

    # Aguarda SSE terminar — ORCH já deve ter chegado e feito o break.
    # shield() evita cancelar sse_task se wait_for atingir timeout
    try:
        await asyncio.wait_for(asyncio.shield(sse_task), timeout=15.0)
    except Exception as exc:
        # G10: não swallow silencioso — registra mas não propaga
        logger.warning("[CHAINLIT] SSE task não encerrou em 15s: %s", exc)

    # Fecha steps que ficaram abertos (ex.: nó falhou antes de emitir EXIT)
    # Garante que a UI não exiba steps suspensos após a resposta final
    for step in pending_steps.values():
        try:
            step.name = f"⚠️ {step.name} [sem EXIT]"
            await step.__aexit__(None, None, None)
        except Exception:
            pass

    await cl.Message(content=response_text).send()
