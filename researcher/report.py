import re

from .contracts import parse_json

URL = re.compile(r"https?://[^\s)\]>\"'|]+")


# A seção de cobertura vem do script, logo antes das fontes. Sem seção de fontes, vai no fim.
def add_coverage(report, coverage):
    if "## Fontes" in report:
        return report.replace("## Fontes", f"{coverage}\n\n## Fontes", 1)
    return f"{report.rstrip()}\n\n{coverage}\n"


def save_report(run_dir, text):
    path = run_dir / "relatorio.md"
    path.write_text(text, encoding="utf-8")
    return path


# Todo conflito da análise tem que chegar ao relatório, um item por conflito na seção "Em disputa".
def check_disputes(report, analysis):
    try:
        expected = len(parse_json(analysis)["conflicts"])
    except (ValueError, KeyError, TypeError):
        return
    section = report.split("## Em disputa", 1)[1].split("\n## ", 1)[0] if "## Em disputa" in report else ""
    listed = len(re.findall(r"^- \*\*", section, re.MULTILINE))
    print(f"em disputa: {expected} na análise, {listed} no relatório")


# Todo link do relatório tem que ter vindo de uma busca. Link de fora foi inventado no caminho.
def check_sources(report, findings):
    found = {url.rstrip(".,;:") for url in URL.findall(report)}
    known = {f["url"] for f in findings}
    outside = sorted(found - known)
    print(f"links no relatório: {len(found)}; vindos das buscas: {len(found) - len(outside)}")
    for url in outside:
        print(f"    fora das buscas: {url}")
