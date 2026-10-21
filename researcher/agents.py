from claude_agent_sdk import AgentDefinition

from .config import ANALYSIS_MAX_TURNS, MODEL, PROMPTS_DIR, SEARCH_MAX_TURNS


def load_prompt(name):
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# A description é o que o coordenador lê para decidir quando chamar cada subagente.
# Com tools=[] o subagente roda sem ferramenta nenhuma: só lê o pedido e responde.
AGENTS = {
    "busca": AgentDefinition(
        description=(
            "Pesquisa uma peça de hardware na internet e devolve achados com fonte. "
            "Chame uma vez por peça; várias buscas podem rodar ao mesmo tempo."
        ),
        prompt=load_prompt("search"),
        tools=["WebSearch", "WebFetch"],
        model=MODEL,
        maxTurns=SEARCH_MAX_TURNS,
    ),
    "analista": AgentDefinition(
        description="Compara os achados das buscas por peça e critério e aponta conflitos e lacunas. Não acessa a internet.",
        prompt=load_prompt("analyst"),
        tools=[],
        model=MODEL,
        maxTurns=ANALYSIS_MAX_TURNS,
    ),
    "sintetizador": AgentDefinition(
        description="Escreve o relatório final em Markdown a partir da análise. Não acessa a internet.",
        prompt=load_prompt("synthesizer"),
        tools=[],
        model=MODEL,
        maxTurns=ANALYSIS_MAX_TURNS,
    ),
}
