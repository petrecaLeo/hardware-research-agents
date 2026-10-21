import json
import time
from textwrap import indent

from .contracts import findings, rows

# A ferramenta que chama subagentes se chamava "Task" até o Claude Code 2.1.63; hoje é "Agent".
AGENT_TOOLS = {"Agent", "Task"}


class Progress:
    """Mostra o que cada agente faz e guarda o que cada subagente devolveu."""

    def __init__(self):
        self.tasks = {}  # id da chamada Agent -> (tipo do subagente, descrição, início)
        self.outputs = {}  # tipo do subagente -> textos devolvidos
        self.search_durations = []
        self.search_start = self.search_end = None

    def all_findings(self):
        return [f for text in self.outputs.get("busca", []) for f in findings(text)]

    # Mensagens de dentro de um subagente trazem o parent_tool_use_id: o id da chamada Agent que o criou.
    def tool_use(self, block, parent_id):
        if block.name in AGENT_TOOLS:
            agent, prompt = block.input.get("subagent_type"), block.input.get("prompt", "")
            self.tasks[block.id] = (agent, block.input.get("description", ""), time.monotonic())
            print(f"[coordenador -> {agent}] {block.input.get('description', '')}")
            if agent == "busca":
                self.search_start = self.search_start or time.monotonic()
                print(indent(prompt, "    "))
            elif agent == "analista":
                self.show_relay(prompt, self.all_findings(), "das buscas")
            else:
                self.show_relay(prompt, rows(self.outputs.get("analista", [""])[-1]), "do analista")
        elif parent_id:
            agent, description, _ = self.tasks.get(parent_id, ("subagente", "", 0))
            detail = block.input.get("query") or block.input.get("url")
            print(f"    [{agent}: {description}] {block.name}: {detail}")
        else:
            print(f"[coordenador] {block.name}: {block.input}")

    # O coordenador repassa os achados copiando o texto. Aqui se vê quantos trechos chegaram inteiros.
    def show_relay(self, prompt, items, origin):
        kept = sum(
            1
            for f in items
            if f["quote"][:40] in prompt or json.dumps(f["quote"], ensure_ascii=False)[1:41] in prompt
        )
        print(f"    pedido com {len(prompt)} caracteres; trechos {origin} repassados: {kept} de {len(items)}")

    # tool_use_result traz a resposta crua do subagente, antes de o coordenador ler e resumir.
    def tool_result(self, tool_use_id, result):
        if tool_use_id not in self.tasks:
            return
        agent, description, start = self.tasks[tool_use_id]
        if isinstance(result, dict):
            text = "".join(part.get("text", "") for part in result.get("content", []))
        else:
            text = str(result)
        self.outputs.setdefault(agent, []).append(text)
        seconds = time.monotonic() - start
        print(f"[{agent}: {description}] terminou em {seconds:.0f} s")
        if agent == "busca":
            self.search_durations.append(seconds)
            self.search_end = time.monotonic()

    def show_timing(self):
        if not self.search_durations:
            return
        window = self.search_end - self.search_start
        print(
            f"buscas: {window:.0f} s do início da primeira ao fim da última"
            f" (soma das {len(self.search_durations)}: {sum(self.search_durations):.0f} s)"
        )
