from datetime import datetime
from functools import partial

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
from .config import COORDINATOR_MAX_TURNS, ENV, MAX_BUDGET_USD, MODEL, REPORTS_DIR, ROOT_DIR
from .contracts import enforce_contract
from .cost import cost_summary
from .coverage import coverage_section
from .guards import WebGuard
from .handoff import Handoff
from .progress import Progress
from .report import add_coverage, check_disputes, check_quotes, check_sources, save_report

WEB_TOOLS = ["WebSearch", "WebFetch"]
FILE_TOOLS = ["Read", "Write", "Edit"]
SEARCH_MODES = {
    "paralelo": (
        'chame o agente "busca" para todas as peças na mesma resposta, com várias chamadas Agent de uma vez, '
        "para as buscas rodarem ao mesmo tempo."
    ),
    "sequencial": 'chame o agente "busca" para uma peça por vez e espere a resposta antes de chamar a próxima.',
}


def build_options(mode, guard, handoff, emit):
    system_prompt = (
        load_prompt("coordinator")
        .replace("{modo_busca}", SEARCH_MODES[mode])
        .replace("{pasta}", str(handoff.run_dir))
        .replace("{rascunho}", str(handoff.scratchpad))
    )
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system_prompt,
        agents=AGENTS,
        # As ferramentas precisam existir na sessão para os subagentes herdarem.
        # Os hooks impedem o coordenador de usar a internet e limitam os arquivos à pasta da pesquisa.
        tools=["Agent", *WEB_TOOLS, *FILE_TOOLS],
        allowed_tools=["Agent", *WEB_TOOLS, *FILE_TOOLS],
        cwd=ROOT_DIR,
        # Sem modo explícito, o Claude Code passa cada chamada Agent por um classificador de segurança no Sonnet.
        permission_mode="default",
        setting_sources=[],
        # No Claude Code o Haiku 5.5 sempre pensa (thinking disabled é ignorado); effort low pensa menos.
        effort="low",
        max_turns=COORDINATOR_MAX_TURNS,
        max_budget_usd=MAX_BUDGET_USD,
        env=ENV,
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="|".join(WEB_TOOLS), hooks=[guard.check]),
                HookMatcher(matcher="|".join(FILE_TOOLS), hooks=[handoff.limit_files]),
            ],
            "PostToolUse": [HookMatcher(matcher="Agent|Task", hooks=[handoff.summarize])],
            "SubagentStop": [HookMatcher(hooks=[partial(enforce_contract, emit), handoff.save])],
        },
    )


# Cada passo vira um evento (um dict com "type") entregue ao emit: o terminal imprime, a tela desenha.
async def research(request, emit, mode="paralelo", simulate_timeout=False):
    run_dir = REPORTS_DIR / f"{datetime.now():%Y-%m-%d-%H%M%S}"
    run_dir.mkdir(parents=True)
    emit({"type": "start", "request": request, "mode": mode, "run_dir": str(run_dir)})
    handoff = Handoff(run_dir, emit)
    guard = WebGuard(emit, simulate_timeout)
    progress = Progress(emit, handoff, guard.timed_out)
    result = None
    async with ClaudeSDKClient(options=build_options(mode, guard, handoff, emit)) as client:
        await client.query(request)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        progress.tool_use(block, message.parent_tool_use_id)
            elif isinstance(message, UserMessage):
                for block in message.content if isinstance(message.content, list) else []:
                    if isinstance(block, ToolResultBlock):
                        progress.tool_result(block, message.tool_use_result)
            elif isinstance(message, ResultMessage):
                emit({"type": "done", "result": message.result, "subtype": message.subtype, "errors": message.errors})
                result = message

    coverage = coverage_section(progress.searches, guard.timed_out)
    reports = progress.outputs.get("sintetizador")
    if reports:
        report = add_coverage(reports[-1], coverage)
        emit({"type": "report", "markdown": report, "path": str(save_report(run_dir, report))})
        analysis = progress.outputs.get("analista", [""])[-1]
        emit(
            {
                "type": "checks",
                "links": check_sources(report, progress.all_findings()),
                "disputes": check_disputes(report, analysis),
                "quotes": check_quotes(analysis),
            }
        )
    else:
        emit({"type": "no_report", "coverage": coverage})
    progress.timing()
    if result:
        emit({"type": "cost", **cost_summary(result)})
