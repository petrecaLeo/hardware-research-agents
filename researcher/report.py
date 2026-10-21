import re
from datetime import datetime

from .config import REPORTS_DIR

URL = re.compile(r"https?://[^\s)\]>\"'|]+")


def save_report(text):
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{datetime.now():%Y-%m-%d-%H%M%S}.md"
    path.write_text(text, encoding="utf-8")
    return path


# Todo link do relatório tem que ter vindo de uma busca. Link de fora foi inventado no caminho.
def check_sources(report, findings):
    found = {url.rstrip(".,;:") for url in URL.findall(report)}
    known = {f["url"] for f in findings}
    outside = sorted(found - known)
    print(f"links no relatório: {len(found)}; vindos das buscas: {len(found) - len(outside)}")
    for url in outside:
        print(f"    fora das buscas: {url}")
