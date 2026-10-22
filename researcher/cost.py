from .config import CACHE_READ_FACTOR, CACHE_WRITE_FACTOR, PRICES, WEB_SEARCH_PRICE


# Devolve o custo e se quem calculou foi o SDK (modelo sem preço em config.PRICES).
def model_cost(model, usage):
    prices = PRICES.get(usage.get("canonicalModel", model))
    if prices is None:
        return usage["costUSD"], True
    price_in, price_out = prices
    tokens = (
        usage["inputTokens"] * price_in
        + usage["cacheCreationInputTokens"] * price_in * CACHE_WRITE_FACTOR
        + usage["cacheReadInputTokens"] * price_in * CACHE_READ_FACTOR
        + usage["outputTokens"] * price_out
    ) / 1_000_000
    return tokens + usage["webSearchRequests"] * WEB_SEARCH_PRICE, False


# O model_usage soma todas as chamadas da pesquisa: coordenador, subagentes e as internas do Claude Code.
def cost_summary(result):
    models = []
    for model, usage in (result.model_usage or {}).items():
        cost, by_sdk = model_cost(model, usage)
        models.append(
            {
                "model": model,
                "input": usage["inputTokens"],
                "output": usage["outputTokens"],
                "cache_read": usage["cacheReadInputTokens"],
                "cache_write": usage["cacheCreationInputTokens"],
                "web_searches": usage["webSearchRequests"],
                "cost": cost,
                "by_sdk": by_sdk,
            }
        )
    return {
        "models": models,
        "total": sum(m["cost"] for m in models),
        "sdk_total": result.total_cost_usd or 0,
        "turns": result.num_turns,
        "seconds": result.duration_ms / 1000,
    }
