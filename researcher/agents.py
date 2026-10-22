from datetime import date

from claude_agent_sdk import AgentDefinition

from .config import ANALYSIS_MAX_TURNS, MODEL, PROMPTS_DIR, SEARCH_MAX_TURNS


def load_prompt(name):
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").replace("{hoje}", f"{date.today():%d/%m/%Y}")


# A description é o que o coordenador lê para decidir quando chamar cada subagente.
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
        description=(
            "Lê os arquivos das buscas e separa, por peça e critério, o que está confirmado, em disputa e sem dado. "
            "Não acessa a internet."
        ),
        prompt=load_prompt("analyst"),
        tools=["Read"],
        model=MODEL,
        maxTurns=ANALYSIS_MAX_TURNS,
    ),
    "sintetizador": AgentDefinition(
        description="Lê o arquivo da análise e escreve o relatório final em Markdown. Não acessa a internet.",
        prompt=load_prompt("synthesizer"),
        tools=["Read"],
        model=MODEL,
        maxTurns=ANALYSIS_MAX_TURNS,
    ),
}
