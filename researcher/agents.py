from claude_agent_sdk import AgentDefinition

from .config import MODEL, PROMPTS_DIR, SEARCH_MAX_TURNS


def load_prompt(name):
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# A description é o que o coordenador lê para decidir quando chamar cada subagente.
AGENTS = {
    "busca": AgentDefinition(
        description="Pesquisa uma peça de hardware na internet e devolve achados com fonte. Chame uma vez por peça.",
        prompt=load_prompt("search"),
        tools=["WebSearch", "WebFetch"],
        model=MODEL,
        maxTurns=SEARCH_MAX_TURNS,
    ),
}
