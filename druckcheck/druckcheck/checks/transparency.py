"""Prüfungen: Transparenzen und weiß überdruckende Objekte."""

from __future__ import annotations

from ..document import Document
from ..models import CheckResult, Finding, Status, make_result

KIND_DE = {"fill": "Fläche", "stroke": "Linie", "text": "Text"}


def check_transparency(doc: Document) -> CheckResult:
    findings = []
    for info in doc.pages:
        reasons = info.content.transparency
        if reasons:
            findings.append(Finding(
                "transparency.used", Status.YELLOW,
                f"Seite {info.number} enthält Transparenzen ({', '.join(reasons)}). Moderne "
                "Druckereien verarbeiten das meist problemlos; bei älteren Systemen kann es zu "
                "Farbabweichungen oder feinen Linien kommen.",
                page=info.number, data={"reasons": reasons}))
    return make_result("transparency", "Transparenzen", findings, "Keine Transparenzen im Dokument.")


def check_overprint(doc: Document) -> CheckResult:
    findings = []
    for info in doc.pages:
        events = info.content.overprint_white
        if events:
            kinds = sorted({KIND_DE[e.kind] for e in events})
            findings.append(Finding(
                "overprint.white", Status.RED,
                f"Seite {info.number}: Weiße Elemente ({', '.join(kinds)}) sind auf \"Überdrucken\" "
                "gestellt. Sie verschwinden im Druck komplett.",
                page=info.number, data={"count": len(events), "kinds": kinds}))
    return make_result("overprint", "Überdrucken", findings, "Keine weißen Objekte auf Überdrucken.")
