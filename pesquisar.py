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
    parser.add_argument(
        "--simular-timeout",
        action="store_true",
        help="a primeira busca a usar a internet expira na hora, para ver o relatório com cobertura parcial",
    )
    args = parser.parse_args()
    mode = "sequencial" if args.sequencial else "paralelo"
    asyncio.run(research(args.pedido, mode, args.simular_timeout))
