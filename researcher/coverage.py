from .contracts import parse_json

# Quando o subagente não termina, o Claude Code devolve um aviso no lugar da resposta.
CLAUDE_CODE_NOTES = {
    "terminated early due to an API error": "erro da API",
    "turn limit": "parou no limite de voltas",
}


# A cobertura sai do que aconteceu (tempo esgotado no guarda, aviso do Claude Code, campo error),
# não só do que o modelo escreveu: falha que ninguém anota some do relatório.
def search_coverage(description, agent_id, text, timed_out):
    try:
        data = parse_json(text)
    except ValueError:
        data = {}
    part = data.get("part") or description
    error = data.get("error") if isinstance(data.get("error"), dict) else None
    note = next((reason for marker, reason in CLAUDE_CODE_NOTES.items() if marker in text), None)
    if agent_id in timed_out:
        reason, retryable = "busca expirou", True
    elif error:
        reason, retryable = error.get("failed") or "erro sem descrição", error.get("retryable")
    elif note:
        reason, retryable = note, False
    elif not data:
        reason, retryable = "resposta fora do formato", False
    else:
        return part, "cobertura completa"
    label = f"{'parcial' if data.get('findings') else 'sem dados'}: {reason}"
    return part, label + (" (dá para tentar de novo)" if retryable else "")


def coverage_section(searches, timed_out):
    lines = [f"- {part}: {label}" for part, label in (search_coverage(*s, timed_out) for s in searches)]
    return "## Cobertura\n\n" + ("\n".join(lines) or "Nenhuma busca rodou.")
