"""Prüfung: Sind alle verwendeten Schriften eingebettet?"""

from __future__ import annotations

from ..document import Document
from ..models import CheckResult, Finding, Status, make_result

EMBED_KEYS = ("/FontFile", "/FontFile2", "/FontFile3")


def font_name(font) -> str:
    name = str(font.get("/BaseFont", "/(unbenannt)"))[1:]
    # Teilmengen-Präfix "ABCDEF+" entfernen
    if len(name) > 7 and name[6] == "+" and name[:6].isupper():
        name = name[7:]
    return name


def is_embedded(font) -> bool:
    subtype = str(font.get("/Subtype", ""))
    if subtype == "/Type3":
        return True   # Glyphen sind als Zeichenanweisungen im PDF enthalten
    target = font
    if subtype == "/Type0":
        descendants = font.get("/DescendantFonts")
        if not descendants:
            return False
        target = descendants[0]
    descriptor = target.get("/FontDescriptor")
    if descriptor is None:
        return False
    return any(k in descriptor for k in EMBED_KEYS)


def check_fonts(doc: Document) -> CheckResult:
    fonts: dict[str, dict] = {}
    for info in doc.pages:
        for font in info.content.fonts_used.values():
            name = font_name(font)
            entry = fonts.setdefault(name, {"embedded": True, "pages": set(),
                                            "type": str(font.get("/Subtype", ""))[1:]})
            entry["pages"].add(info.number)
            if not is_embedded(font):
                entry["embedded"] = False

    findings = []
    missing = sorted(n for n, e in fonts.items() if not e["embedded"])
    for name in missing:
        pages = sorted(fonts[name]["pages"])
        findings.append(Finding(
            "fonts.not_embedded", Status.RED,
            f"Die Schrift \"{name}\" ist nicht eingebettet (Seite {', '.join(map(str, pages))}). "
            "Die Druckerei ersetzt sie sonst durch eine andere Schrift.",
            page=pages[0], data={"font": name, "pages": pages}))

    measurements = {"fonts": [
        {"name": n, "embedded": e["embedded"], "type": e["type"], "pages": sorted(e["pages"])}
        for n, e in sorted(fonts.items())]}
    ok = ("Alle Schriften sind eingebettet." if fonts
          else "Keine Schriften verwendet (Texte sind in Pfade umgewandelt oder es gibt keinen Text).")
    return make_result("fonts", "Schriften", findings, ok, measurements)
