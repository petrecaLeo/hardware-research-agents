import json

ITEM_KEYS = {"claim", "quote", "url", "published_at"}
ERROR_KEYS = {"attempted", "failed", "retryable"}
# Campos que cada subagente tem que devolver, e onde ficam os itens com fonte.
CONTRACTS = {
    "busca": ({"part", "findings", "gaps", "error"}, "findings"),
    "analista": ({"criteria", "rows", "conflicts", "gaps"}, "rows"),
}


def parse_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("a resposta não tem um objeto JSON")
    return json.loads(text[start : end + 1])


def problems(agent_type, text):
    try:
        data = parse_json(text)
    except ValueError as error:
        return [f"JSON inválido ({error})"]
    fields, items_field = CONTRACTS[agent_type]
    if not isinstance(data, dict) or not fields <= data.keys():
        return [f"o objeto precisa dos campos {sorted(fields)}"]
    found = []
    error = data.get("error")
    if error is not None and (not isinstance(error, dict) or not ERROR_KEYS <= error.keys()):
        found.append(f"error precisa ser null ou ter {sorted(ERROR_KEYS)}")
    for i, item in enumerate(data[items_field]):
        if not isinstance(item, dict) or not ITEM_KEYS <= item.keys():
            found.append(f"{items_field}[{i}] precisa de {sorted(ITEM_KEYS)}")
        elif not str(item["url"]).startswith("http") or not item["quote"]:
            found.append(f"{items_field}[{i}] precisa de url e de trecho citado")
    if agent_type == "analista":
        found += split_problems(data)
    return found


# Cada peça e critério fica num lugar só: confirmado (rows), em disputa (conflicts) ou sem dado (gaps).
def split_problems(data):
    found = []
    confirmed = {(r.get("part"), r.get("criterion")) for r in data["rows"] if isinstance(r, dict)}
    for i, conflict in enumerate(data["conflicts"]):
        values = conflict.get("values", []) if isinstance(conflict, dict) else []
        if len(values) < 2:
            found.append(f"conflicts[{i}] precisa de pelo menos dois valores")
        elif not all(isinstance(v, dict) and str(v.get("url")).startswith("http") and v.get("quote") for v in values):
            found.append(f"conflicts[{i}]: cada valor precisa de url e de trecho citado")
        if isinstance(conflict, dict) and (conflict.get("part"), conflict.get("criterion")) in confirmed:
            found.append(f"conflicts[{i}] também está em rows: um valor em disputa não entra em rows")
    return found


def items(text, field):
    try:
        return [item for item in parse_json(text)[field] if isinstance(item, dict) and item.get("quote")]
    except (ValueError, KeyError, TypeError):
        return []


def findings(text):
    return items(text, "findings")


def rows(text):
    return items(text, "rows")


# SubagentStop: antes de a busca ou o analista terminar, confere se a resposta segue o contrato.
# Se não seguir, o subagente recebe a lista de problemas e tenta de novo, uma vez só.
async def enforce_contract(input_data, tool_use_id, context):
    agent_type = input_data["agent_type"]
    if agent_type not in CONTRACTS:
        return {}
    found = problems(agent_type, input_data.get("last_assistant_message", ""))
    if not found:
        return {}
    if input_data["stop_hook_active"]:
        print(f"    [contrato] {agent_type} continua fora do formato: {found[:3]}")
        return {}
    print(f"    [contrato] {agent_type} fora do formato, pedindo correção: {found[:3]}")
    return {
        "decision": "block",
        "reason": "Sua resposta não segue o formato pedido: " + "; ".join(found[:5]) + ". Devolva só o JSON corrigido.",
    }
