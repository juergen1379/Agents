"""Prüfung: Texte und Bildelemente innerhalb des Sicherheitsabstands."""

from __future__ import annotations

from ..document import Document
from ..models import CheckResult, Finding, Status, make_result
from ..pdfdata import Box, mm, pt
from ..render import text_lines

BACKGROUND_SHARE = 0.5     # Bilder, die mehr als die Hälfte bedecken, gelten als Hintergrund
EDGE_EPS_PT = 0.5


def safe_box(trim: Box, doc: Document, scale: float) -> Box:
    s = doc.product.safety
    return trim.inset(pt(s.top * scale), pt(s.right * scale), pt(s.bottom * scale), pt(s.left * scale))


def edge_distance_mm(inner: Box, trim: Box, scale: float) -> float:
    """Kleinster Abstand eines Elements zum Endformatrand (im Endformat, negativ = ragt hinaus)."""
    return min(inner.x0 - trim.x0, trim.x1 - inner.x1, inner.y0 - trim.y0, trim.y1 - inner.y1) \
        * (25.4 / 72) / scale


def check_safety_margin(doc: Document) -> CheckResult:
    product = doc.product
    findings: list[Finding] = []
    for info in doc.pages:
        fmt = info.fmt
        if not fmt.ok:
            findings.append(Finding(
                "safety.not_checked", Status.YELLOW,
                f"Seite {info.number}: Sicherheitsabstand nicht prüfbar, weil das Format nicht passt.",
                page=info.number))
            continue
        trim, scale = fmt.trim, fmt.scale
        safe = safe_box(trim, doc, scale)
        cut, near = [], []
        for line in text_lines(doc.fitz_page(info.number)):
            if not line.bbox.intersects(trim):
                continue   # liegt komplett im Beschnitt / außerhalb → wird ohnehin abgeschnitten
            if safe.contains(line.bbox, tol=EDGE_EPS_PT):
                continue
            entry = {"text": line.text[:60], "distance_mm": round(edge_distance_mm(line.bbox, trim, scale), 1)}
            (cut if not trim.contains(line.bbox, tol=EDGE_EPS_PT) else near).append(entry)
        if cut:
            findings.append(Finding(
                "safety.text_cut", Status.RED,
                f"Seite {info.number}: {_n(len(cut), 'Textzeile ragt', 'Textzeilen ragen')} über den Rand "
                f"des Endformats hinaus und {'wird' if len(cut) == 1 else 'werden'} angeschnitten "
                f"(z. B. \"{cut[0]['text']}\").",
                page=info.number, data={"lines": cut}))
        if near:
            findings.append(Finding(
                "safety.text_in_margin", Status.YELLOW,
                f"Seite {info.number}: {_n(len(near), 'Textzeile liegt', 'Textzeilen liegen')} näher als "
                f"{_mm(product.safety.min)} mm am Rand (z. B. \"{near[0]['text']}\"). "
                "Durch Schnitttoleranzen können sie angeschnitten werden.",
                page=info.number, data={"lines": near, "safety_mm": product.safety.__dict__}))

        images_near = []
        trim_area = trim.area
        for img in info.content.images:
            if img.is_mask:
                continue
            vis = img.bbox.intersect(trim)
            if vis is None or vis.area >= BACKGROUND_SHARE * trim_area:
                continue
            if edge_distance_mm(img.bbox, trim, 1.0) * 72 / 25.4 <= EDGE_EPS_PT:
                continue   # randabfallend gemeint – das bewertet die Beschnittprüfung
            if safe.contains(img.bbox, tol=EDGE_EPS_PT):
                continue
            images_near.append({"name": img.name,
                                "distance_mm": round(edge_distance_mm(img.bbox, trim, scale), 1),
                                "size_mm": [round(mm(img.bbox.width) / scale, 1),
                                            round(mm(img.bbox.height) / scale, 1)]})
        if images_near:
            findings.append(Finding(
                "safety.image_in_margin", Status.YELLOW,
                f"Seite {info.number}: {_n(len(images_near), 'Bild (z. B. ein Logo) liegt', 'Bilder liegen')} "
                f"im Sicherheitsabstand von {_mm(product.safety.min)} mm zum Rand.",
                page=info.number, data={"images": images_near}))

    return make_result("safety", "Sicherheitsabstand", findings,
                       "Alle Texte und Bildelemente halten den Sicherheitsabstand ein.",
                       {"safety_mm": product.safety.__dict__})


def _n(n: int, singular: str, plural: str) -> str:
    return f"1 {singular}" if n == 1 else f"{n} {plural}"


def _mm(v: float) -> str:
    s = f"{v:.1f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s
