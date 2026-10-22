import re

from .contracts import parse_json

URL = re.compile(r"https?://[^\s)\]>\"'|]+")
# Número solto, com separador de milhar ou decimal: "3.768", "R$3,768", "1440p". Não pega o 6 de "GDDR6".
NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*")


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
        return None
    section = report.split("## Em disputa", 1)[1].split("\n## ", 1)[0] if "## Em disputa" in report else ""
    return {"analysis": expected, "report": len(re.findall(r"^- \*\*", section, re.MULTILINE))}


# Todo link do relatório tem que ter vindo de uma busca. Link de fora foi inventado no caminho.
def check_sources(report, findings):
    found = {url.rstrip(".,;:") for url in URL.findall(report)}
    known = {f["url"] for f in findings}
    return {"total": len(found), "outside": sorted(found - known)}


# "R$ 2.849,00", "2,849" e "2849" viram o mesmo número.
def normalize(number):
    return re.sub(r"[.,]", "", re.sub(r"[.,]0+$", "", number))


# O primeiro número do valor tem que aparecer no trecho citado. Se não aparece, o trecho não sustenta o valor.
def check_quotes(analysis):
    try:
        data = parse_json(analysis)
        items = data["rows"] + [
            {"part": c["part"], "criterion": c["criterion"], **v} for c in data["conflicts"] for v in c["values"]
        ]
    except (ValueError, KeyError, TypeError):
        return None
    checked, mismatched = 0, []
    for item in items:
        numbers = NUMBER.findall(str(item.get("value", "")))
        if not numbers:
            continue
        checked += 1
        if normalize(numbers[0]) not in {normalize(n) for n in NUMBER.findall(str(item.get("quote", "")))}:
            mismatched.append({key: item.get(key) for key in ("part", "criterion", "value", "quote")})
    return {"checked": checked, "mismatched": mismatched}
