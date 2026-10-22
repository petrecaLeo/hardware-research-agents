import json
import re
from pathlib import Path

from .contracts import parse_json
from .guards import deny

# O relatório do sintetizador o script salva no fim, já com a cobertura.
SAVED_AGENTS = {"busca", "analista"}
SEARCH_DIR, ANALYSIS_FILE = "buscas", "analise.json"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


class Handoff:
    """Salva o que a busca e o analista devolvem na pasta da pesquisa. O coordenador recebe só
    o caminho e um resumo: não carrega os achados na conversa nem tem o que copiar."""

    def __init__(self, run_dir, emit):
        self.run_dir = run_dir
        self.emit = emit
        self.scratchpad = run_dir / "rascunho.md"
        self.texts = {}  # agent_id -> resposta completa do subagente
        self.paths = {}  # agent_id -> arquivo onde ela foi salva

    # SubagentStop. Se o contrato pedir correção, a parada seguinte sobrescreve o arquivo.
    async def save(self, input_data, tool_use_id, context):
        agent_type, agent_id = input_data["agent_type"], input_data["agent_id"]
        if agent_type not in SAVED_AGENTS:
            return {}
        text = input_data.get("last_assistant_message", "")
        self.texts[agent_id] = text
        try:
            data = parse_json(text)
            content = json.dumps(data, ensure_ascii=False, indent=2)
        except ValueError:
            data, content = {}, text
        if agent_id not in self.paths:
            self.paths[agent_id] = self.new_path(agent_type, data.get("part") or agent_id)
        self.paths[agent_id].parent.mkdir(exist_ok=True)
        self.paths[agent_id].write_text(content, encoding="utf-8")
        return {}

    def new_path(self, agent_type, part):
        if agent_type == "analista":
            return self.run_dir / ANALYSIS_FILE
        number = sum(1 for path in self.paths.values() if path.parent.name == SEARCH_DIR) + 1
        return self.run_dir / SEARCH_DIR / f"{number}-{slug(part)}.json"

    # PostToolUse no Agent: troca a resposta inteira do subagente por um resumo com o caminho do arquivo.
    async def summarize(self, input_data, tool_use_id, context):
        response = input_data.get("tool_response")
        agent_id = response.get("agentId") if isinstance(response, dict) else None
        if agent_id not in self.paths:
            return {}
        summary = describe(self.paths[agent_id], self.texts[agent_id])
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": {**response, "content": [{"type": "text", "text": summary}]},
            }
        }

    # PreToolUse em Read, Write e Edit: o coordenador só mexe no rascunho;
    # os subagentes só leem arquivos desta pesquisa.
    async def limit_files(self, input_data, tool_use_id, context):
        path = Path(input_data["tool_input"].get("file_path", "")).resolve()
        if input_data.get("agent_id") is None:
            if path == self.scratchpad.resolve():
                return {}
            self.notify(tool_use_id, f"o coordenador tentou usar {input_data['tool_name']} em {path.name}")
            return deny(f"Você só usa o rascunho ({self.scratchpad}). Passe os caminhos dos arquivos aos agentes.")
        if path.is_relative_to(self.run_dir.resolve()):
            return {}
        self.notify(tool_use_id, f"um subagente tentou ler fora da pasta da pesquisa: {path}")
        return deny(f"Leia só os arquivos da pasta desta pesquisa: {self.run_dir}")

    def notify(self, tool_use_id, text):
        self.emit({"type": "notice", "source": "arquivos", "tool_id": tool_use_id, "text": text})


def describe(path, text):
    try:
        data = parse_json(text)
    except ValueError:
        return f"Resposta salva em {path}, mas fora do formato JSON."
    if "findings" in data:
        summary = f"Busca salva em {path}: {len(data['findings'])} achados, {len(data.get('gaps', []))} lacunas"
        error = data.get("error")
        if isinstance(error, dict):
            summary += f"; falhou: {error.get('failed')} (dá para tentar de novo: {error.get('retryable')})"
        return summary + "."
    return (
        f"Análise salva em {path}: {len(data.get('rows', []))} valores confirmados, "
        f"{len(data.get('conflicts', []))} em disputa, {len(data.get('gaps', []))} lacunas."
    )
