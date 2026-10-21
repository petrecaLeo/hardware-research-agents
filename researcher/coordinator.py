from datetime import date

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .agents import AGENTS, load_prompt
from .config import COORDINATOR_MAX_TURNS, ENV, MAX_BUDGET_USD, MODEL
from .contracts import enforce_contract
from .cost import print_cost
from .coverage import coverage_section
from .guards import WebGuard
from .progress import Progress
from .report import add_coverage, check_sources, save_report

WEB_TOOLS = ["WebSearch", "WebFetch"]
SEARCH_MODES = {
    "paralelo": (
        'chame o agente "busca" para todas as peças na mesma resposta, com várias chamadas Agent de uma vez, '
        "para as buscas rodarem ao mesmo tempo."
    ),
    "sequencial": 'chame o agente "busca" para uma peça por vez e espere a resposta antes de chamar a próxima.',
}


def build_options(mode, guard):
    system_prompt = (
        load_prompt("coordinator")
        .replace("{hoje}", f"{date.today():%d/%m/%Y}")
        .replace("{modo_busca}", SEARCH_MODES[mode])
    )
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system_prompt,
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
        hooks={
            "PreToolUse": [HookMatcher(matcher="|".join(WEB_TOOLS), hooks=[guard.check])],
            "SubagentStop": [HookMatcher(hooks=[enforce_contract])],
        },
    )


async def research(request, mode="paralelo", simulate_timeout=False):
    print(f"Pedido: {request}\nBuscas: {mode}\n")
    progress = Progress()
    guard = WebGuard(simulate_timeout)
    result = None
    async with ClaudeSDKClient(options=build_options(mode, guard)) as client:
        await client.query(request)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        progress.tool_use(block, message.parent_tool_use_id)
            elif isinstance(message, UserMessage) and message.parent_tool_use_id is None:
                for block in message.content if isinstance(message.content, list) else []:
                    if isinstance(block, ToolResultBlock):
                        progress.tool_result(block.tool_use_id, message.tool_use_result or block.content)
            elif isinstance(message, ResultMessage):
                if message.subtype != "success":
                    print(f"\nParou antes do fim: {message.subtype} {message.errors or ''}")
                print(f"\nCoordenador: {message.result}")
                result = message

    coverage = coverage_section(progress.searches, guard.timed_out)
    reports = progress.outputs.get("sintetizador")
    if reports:
        report = add_coverage(reports[-1], coverage)
        print(f"\n{report}\n")
        print(f"relatório salvo em {save_report(report)}")
        check_sources(report, progress.all_findings())
    else:
        print(f"\nSem relatório: o sintetizador não terminou.\n\n{coverage}\n")
    progress.show_timing()
    if result:
        print_cost(result)
