from collections import Counter

from .config import TOOL_LIMITS

uses = Counter()


def deny(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# PreToolUse nas ferramentas de internet. O agent_id só vem quando quem chama é um subagente:
# sem ele, é o coordenador tentando pesquisar sozinho.
async def limit_web_tools(input_data, tool_use_id, context):
    tool = input_data["tool_name"]
    agent = input_data.get("agent_id")
    if agent is None:
        print(f"    [guarda] o coordenador tentou usar {tool}")
        return deny(
            "O coordenador não acessa a internet. "
            "Chame o agente busca com a peça, o uso, o orçamento e a data de hoje."
        )
    uses[agent, tool] += 1
    if uses[agent, tool] > TOOL_LIMITS[tool]:
        print(f"    [guarda] limite de {tool} atingido")
        return deny(f"Limite de {TOOL_LIMITS[tool]} usos de {tool} atingido. Responda com os achados que já tem.")
    return {}
