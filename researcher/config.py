from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

load_dotenv(ROOT_DIR / ".env")

MODEL = "claude-haiku-5-5"

# US$ por milhão de tokens: (entrada, saída). O Haiku 5.5 cobra 5× acima de 100K tokens de prompt;
# as chamadas daqui ficam abaixo disso.
PRICES = {MODEL: (0.10, 0.50)}
CACHE_WRITE_FACTOR = 1.25
CACHE_READ_FACTOR = 0.1
WEB_SEARCH_PRICE = 0.01

# Quantas vezes cada subagente pode usar cada ferramenta numa pesquisa.
TOOL_LIMITS = {"WebSearch": 3, "WebFetch": 4}
COORDINATOR_MAX_TURNS = 8
SEARCH_MAX_TURNS = 10
MAX_BUDGET_USD = 0.25

ENV = {
    # Chamadas internas do Claude Code, como o resumo da página no WebFetch, também no Haiku 5.5.
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
    "CLAUDE_CODE_SUBAGENT_MODEL": MODEL,
    "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
    # Sem segundo plano: o coordenador espera cada subagente terminar antes de seguir.
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
    # Sem os agentes prontos do Claude Code (general-purpose, Explore...): só os definidos aqui.
    "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
    "ENABLE_TOOL_SEARCH": "false",
}
