import time
from collections import Counter

from .config import SEARCH_TIMEOUT_S, TOOL_LIMITS


def deny(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


class WebGuard:
    """PreToolUse nas ferramentas de internet: barra o coordenador e limita os usos e o tempo de cada busca."""

    def __init__(self, simulate_timeout=False):
        self.simulate_timeout = simulate_timeout
        self.uses = Counter()
        self.deadlines = {}  # agent_id -> momento em que a busca perde o acesso à internet
        self.timed_out = set()  # agent_id das buscas que passaram do tempo

    # O agent_id só vem quando quem chama é um subagente: sem ele, é o coordenador tentando pesquisar sozinho.
    async def check(self, input_data, tool_use_id, context):
        tool = input_data["tool_name"]
        agent = input_data.get("agent_id")
        if agent is None:
            print(f"    [guarda] o coordenador tentou usar {tool}")
            return deny(
                "O coordenador não acessa a internet. "
                "Chame o agente busca com a peça, o uso, o orçamento e a data de hoje."
            )
        if self.out_of_time(agent):
            return deny(
                "Tempo esgotado: a busca passou do limite de tempo. Não use mais ferramentas. "
                "Responda agora com os achados que já tem e preencha error."
            )
        self.uses[agent, tool] += 1
        if self.uses[agent, tool] > TOOL_LIMITS[tool]:
            print(f"    [guarda] limite de {tool} atingido")
            return deny(f"Limite de {TOOL_LIMITS[tool]} usos de {tool} atingido. Responda com os achados que já tem.")
        return {}

    # O relógio começa na primeira ferramenta da busca. O guarda não interrompe uma ferramenta
    # que já está rodando: ele barra a próxima. Com --simular-timeout, a primeira busca já começa sem tempo.
    def out_of_time(self, agent):
        now = time.monotonic()
        if agent not in self.deadlines:
            simulated = self.simulate_timeout and not self.deadlines
            self.deadlines[agent] = now + (0 if simulated else SEARCH_TIMEOUT_S)
        if now < self.deadlines[agent]:
            return False
        if agent not in self.timed_out:
            print(f"    [guarda] tempo esgotado para uma busca{' (simulado)' if self.simulate_timeout else ''}")
            self.timed_out.add(agent)
        return True
