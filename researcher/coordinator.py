from datetime import date
from textwrap import indent

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    ToolUseBlock,
)

from .agents import AGENTS, load_prompt
from .config import COORDINATOR_MAX_TURNS, ENV, MAX_BUDGET_USD, MODEL
from .cost import print_cost
from .guards import limit_web_tools

# A ferramenta que chama subagentes se chamava "Task" até o Claude Code 2.1.63; hoje é "Agent".
AGENT_TOOLS = {"Agent", "Task"}
WEB_TOOLS = ["WebSearch", "WebFetch"]


def build_options():
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=load_prompt("coordinator").replace("{hoje}", f"{date.today():%d/%m/%Y}"),
        agents=AGENTS,
        # As ferramentas de internet precisam existir na sessão para a busca herdar;
        # o guarda impede o coordenador de usá-las.
        tools=["Agent", *WEB_TOOLS],
        allowed_tools=["Agent", *WEB_TOOLS],
        # Sem modo explícito, o Claude Code passa cada chamada Agent por um classificador de segurança no Sonnet.
        permission_mode="default",
        setting_sources=[],
        # No Claude Code o Haiku 5.5 sempre pensa (thinking disabled é ignorado); effort low pensa menos.
        effort="low",
        max_turns=COORDINATOR_MAX_TURNS,
        max_budget_usd=MAX_BUDGET_USD,
        env=ENV,
        hooks={"PreToolUse": [HookMatcher(matcher="|".join(WEB_TOOLS), hooks=[limit_web_tools])]},
    )


# Mensagens de dentro de um subagente trazem o parent_tool_use_id: o id da chamada Agent que o criou.
def show_tool_use(block, parent_id, tasks):
    if block.name in AGENT_TOOLS:
        tasks[block.id] = block.input.get("description", "")
        print(f"[coordenador -> {block.input.get('subagent_type')}] o subagente recebe só isto:")
        print(indent(block.input.get("prompt", ""), "    "))
    elif parent_id:
        detail = block.input.get("query") or block.input.get("url")
        print(f"    [{tasks.get(parent_id, 'subagente')}] {block.name}: {detail}")
    else:
        print(f"[coordenador] {block.name}: {block.input}")


async def research(request):
    print(f"Pedido: {request}\n")
    tasks = {}
    async with ClaudeSDKClient(options=build_options()) as client:
        await client.query(request)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        show_tool_use(block, message.parent_tool_use_id, tasks)
            elif isinstance(message, ResultMessage):
                if message.subtype != "success":
                    print(f"\nParou antes do fim: {message.subtype} {message.errors or ''}")
                print(f"\nResposta do coordenador:\n{message.result}\n")
                print_cost(message)
