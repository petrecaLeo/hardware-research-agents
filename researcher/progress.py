import time

from .contracts import findings, parse_json
from .coverage import search_coverage

# A ferramenta que chama subagentes se chamava "Task" até o Claude Code 2.1.63; hoje é "Agent".
AGENT_TOOLS = {"Agent", "Task"}


def tool_detail(tool_input):
    return tool_input.get("query") or tool_input.get("url") or tool_input.get("file_path") or str(tool_input)


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if isinstance(part, dict))


class Progress:
    """Transforma as mensagens do SDK em eventos e guarda o que cada subagente devolveu."""

    def __init__(self, emit, handoff, timed_out):
        self.emit = emit
        self.handoff = handoff
        self.timed_out = timed_out
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
            agent, description = block.input.get("subagent_type"), block.input.get("description", "")
            self.tasks[block.id] = (agent, description, time.monotonic())
            if agent == "busca":
                self.search_start = self.search_start or time.monotonic()
            self.emit(
                {
                    "type": "agent_start",
                    "id": block.id,
                    "agent": agent,
                    "description": description,
                    "prompt": block.input.get("prompt", ""),
                }
            )
            return
        event = {
            "type": "tool",
            "id": block.id,
            "parent": parent_id,
            "tool": block.name,
            "detail": tool_detail(block.input),
        }
        if parent_id in self.tasks:
            event["agent"], event["description"], _ = self.tasks[parent_id]
        self.emit(event)

    def tool_result(self, block, tool_use_result):
        if block.tool_use_id in self.tasks:
            self.agent_result(block.tool_use_id, tool_use_result or block.content)
        elif block.is_error:
            text = text_of(block.content)
            # As negações dos hooks já viraram aviso, com o motivo curto.
            if "hook error" not in text:
                self.emit({"type": "tool_error", "id": block.tool_use_id, "text": text[:300]})

    # O coordenador recebe um resumo; a resposta completa vem do que o script salvou (handoff.texts).
    # Sem ela (subagente que caiu ou parou no limite de voltas), vale o que veio no tool_use_result.
    def agent_result(self, tool_use_id, result):
        agent, description, start = self.tasks[tool_use_id]
        seconds = time.monotonic() - start
        event = {
            "type": "agent_end",
            "id": tool_use_id,
            "agent": agent,
            "description": description,
            "seconds": round(seconds),
        }
        if isinstance(result, dict):
            agent_id = result.get("agentId")
            text = self.handoff.texts.get(agent_id) or text_of(result.get("content"))
            self.outputs.setdefault(agent, []).append(text)
            event.update(self.outcome(agent, agent_id, description, text))
            if agent_id in self.handoff.paths:
                event["file"] = str(self.handoff.paths[agent_id].relative_to(self.handoff.run_dir))
        else:
            # Quando o subagente cai (por exemplo, erro da API), o resultado é só a mensagem de erro.
            agent_id, text = None, str(result)
            event.update(status="failed", label=text[:200])
        if agent == "busca":
            self.searches.append((description, agent_id, text))
            self.search_durations.append(seconds)
            self.search_end = time.monotonic()
        self.emit(event)

    def outcome(self, agent, agent_id, description, text):
        if agent == "busca":
            _, status, coverage = search_coverage(description, agent_id, text, self.timed_out)
            return {"status": status, "label": f"{len(findings(text))} achados; {coverage}"}
        if agent == "analista":
            try:
                data = parse_json(text)
            except ValueError:
                return {"status": "failed", "label": "resposta fora do formato"}
            counts = [len(data.get(field, [])) for field in ("rows", "conflicts", "gaps")]
            return {"status": "ok", "label": "{} confirmados, {} em disputa, {} sem dado".format(*counts)}
        return {"status": "ok", "label": "relatório recebido"}

    def timing(self):
        if self.search_durations:
            self.emit(
                {
                    "type": "timing",
                    "window": round(self.search_end - self.search_start),
                    "sum": round(sum(self.search_durations)),
                    "count": len(self.search_durations),
                }
            )
