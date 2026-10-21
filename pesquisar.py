import asyncio
import sys

from researcher.coordinator import research

EXAMPLE = "Quero uma placa de vídeo RTX 5060 para jogar em 1440p. Meu orçamento é R$ 2.500."

if __name__ == "__main__":
    asyncio.run(research(sys.argv[1] if len(sys.argv) > 1 else EXAMPLE))
