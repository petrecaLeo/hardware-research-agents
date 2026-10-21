import argparse
import asyncio

from researcher.coordinator import research

EXAMPLE = (
    "Compare as placas de vídeo RTX 5060, RX 9060 XT 8 GB e Arc B580 para jogar em 1440p. "
    "Meu orçamento é R$ 2.500."
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pesquisador de hardware com subagentes.")
    parser.add_argument("pedido", nargs="?", default=EXAMPLE)
    parser.add_argument("--sequencial", action="store_true", help="faz uma busca por vez, para comparar o tempo")
    args = parser.parse_args()
    asyncio.run(research(args.pedido, "sequencial" if args.sequencial else "paralelo"))
