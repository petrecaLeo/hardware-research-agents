from textwrap import indent


def print_event(event):
    match event["type"]:
        case "start":
            print(f"Pedido: {event['request']}\nBuscas: {event['mode']}\nPasta: {event['run_dir']}\n")
        case "agent_start":
            print(f"[coordenador -> {event['agent']}] {event['description']}")
            print(indent(event["prompt"], "    "))
        case "tool" if event["parent"] is None:
            print(f"[coordenador] {event['tool']}: {event['detail']}")
        case "tool":
            who = f"{event.get('agent', 'subagente')}: {event.get('description', '')}"
            print(f"    [{who}] {event['tool']}: {event['detail']}")
        case "tool_error":
            print(f"    [erro de ferramenta] {event['text'][:200]}")
        case "notice":
            print(f"    [{event['source']}] {event['text']}")
        case "agent_end":
            verb = "falhou" if event["status"] == "failed" else "terminou"
            print(f"[{event['agent']}: {event['description']}] {verb} em {event['seconds']} s: {event['label']}")
        case "done":
            if event["subtype"] != "success":
                print(f"\nParou antes do fim: {event['subtype']} {event['errors'] or ''}")
            print(f"\nCoordenador: {event['result']}")
        case "report":
            print(f"\n{event['markdown']}\n\nrelatório salvo em {event['path']}")
        case "no_report":
            print(f"\nSem relatório: o sintetizador não terminou.\n\n{event['coverage']}\n")
        case "checks":
            print_checks(event)
        case "timing":
            print(
                f"buscas: {event['window']} s do início da primeira ao fim da última"
                f" (soma das {event['count']}: {event['sum']} s)"
            )
        case "cost":
            print_cost(event)
        case "error":
            print(f"\nErro: {event['message']}")


def print_checks(event):
    links = event["links"]
    print(f"links no relatório: {links['total']}; vindos das buscas: {links['total'] - len(links['outside'])}")
    for url in links["outside"]:
        print(f"    fora das buscas: {url}")
    if event["disputes"]:
        print(f"em disputa: {event['disputes']['analysis']} na análise, {event['disputes']['report']} no relatório")
    if event["quotes"]:
        quotes = event["quotes"]
        print(f"trechos com o número do valor: {quotes['checked'] - len(quotes['mismatched'])} de {quotes['checked']}")
        for item in quotes["mismatched"]:
            print(f"    {item['part']}, {item['criterion']}: valor {item['value']!r}, trecho {item['quote']!r}")


def print_cost(event):
    for m in event["models"]:
        print(
            f"{m['model']}: {m['input']} in / {m['output']} out / {m['cache_read']} cache read"
            f" / {m['cache_write']} cache write / {m['web_searches']} buscas"
            f" | cost: ${m['cost']:.6f}{' (preço calculado pelo SDK)' if m['by_sdk'] else ''}"
        )
    print(
        f"total: ${event['total']:.6f} (SDK: ${event['sdk_total']:.6f})"
        f" | voltas do coordenador: {event['turns']} | {event['seconds']:.1f} s"
    )
