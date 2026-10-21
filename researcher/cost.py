from .config import CACHE_READ_FACTOR, CACHE_WRITE_FACTOR, PRICES, WEB_SEARCH_PRICE


def model_cost(model, usage):
    prices = PRICES.get(usage.get("canonicalModel", model))
    if prices is None:
        return usage["costUSD"], " (preço calculado pelo SDK)"
    price_in, price_out = prices
    tokens = (
        usage["inputTokens"] * price_in
        + usage["cacheCreationInputTokens"] * price_in * CACHE_WRITE_FACTOR
        + usage["cacheReadInputTokens"] * price_in * CACHE_READ_FACTOR
        + usage["outputTokens"] * price_out
    ) / 1_000_000
    return tokens + usage["webSearchRequests"] * WEB_SEARCH_PRICE, ""


# O model_usage soma todas as chamadas da pesquisa: coordenador, subagentes e as internas do Claude Code.
def print_cost(result):
    total = 0.0
    for model, usage in (result.model_usage or {}).items():
        cost, note = model_cost(model, usage)
        total += cost
        print(
            f"{model}: {usage['inputTokens']} in / {usage['outputTokens']} out"
            f" / {usage['cacheReadInputTokens']} cache read / {usage['cacheCreationInputTokens']} cache write"
            f" / {usage['webSearchRequests']} buscas | cost: ${cost:.6f}{note}"
        )
    print(
        f"total: ${total:.6f} (SDK: ${result.total_cost_usd or 0:.6f})"
        f" | voltas do coordenador: {result.num_turns} | {result.duration_ms / 1000:.1f} s"
    )
