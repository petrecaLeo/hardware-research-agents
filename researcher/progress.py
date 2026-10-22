import time
from textwrap import indent

from .contracts import findings

# A ferramenta que chama subagentes se chamava "Task" até o Claude Code 2.1.63; hoje é "Agent".
AGENT_TOOLS = {"Agent", "Task"}


class Progress:
    """Mostra o que cada agente faz e guarda o que cada subagente devolveu."""

    def __init__(self, full_texts):
        self.full_texts = full_texts  # agent_id -> resposta completa, antes de virar resumo para o coordenador
        self.tasks = {}  # id da chamada Agent -> (tipo do subagente, descrição, início)
        self.outputs = {}  # tipo do subagente -> textos devolvidos
        self.searches = []  # (descrição, agent_id, texto) de cada busca, com ou sem erro
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
            print(indent(prompt, "    "))
            if agent == "busca":
                self.search_start = self.search_start or time.monotonic()
        elif parent_id:
            agent, description, _ = self.tasks.get(parent_id, ("subagente", "", 0))
            detail = block.input.get("query") or block.input.get("url") or block.input.get("file_path")
            print(f"    [{agent}: {description}] {block.name}: {detail}")
        else:
            print(f"[coordenador] {block.name}: {block.input.get('file_path', block.input)}")

    # O coordenador recebe um resumo; a resposta completa vem do que o script salvou (full_texts).
    # Sem ela (subagente que caiu ou parou no limite de voltas), vale o que veio no tool_use_result.
    def tool_result(self, tool_use_id, result):
        if tool_use_id not in self.tasks:
            return
        agent, description, start = self.tasks[tool_use_id]
        seconds = time.monotonic() - start
        if isinstance(result, dict):
            agent_id = result.get("agentId")
            text = self.full_texts.get(agent_id) or "".join(part.get("text", "") for part in result.get("content", []))
            self.outputs.setdefault(agent, []).append(text)
            print(f"[{agent}: {description}] terminou em {seconds:.0f} s")
        else:
            # Quando o subagente cai (por exemplo, erro da API), o resultado é só a mensagem de erro.
            text, agent_id = str(result), None
            print(f"[{agent}: {description}] falhou em {seconds:.0f} s: {text[:200]}")
        if agent == "busca":
            self.searches.append((description, agent_id, text))
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
