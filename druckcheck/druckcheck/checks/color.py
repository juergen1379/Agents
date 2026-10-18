"""Prüfungen: Farbräume (RGB/CMYK/Sonderfarben) und Gesamtfarbauftrag (TAC)."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from ..document import Document
from ..models import CheckResult, Finding, Status, make_result
from ..pdfdata import Box, pt
from ..render import ghostscript_cmyk

KIND_DE = {"image": "Bilder", "vector": "Grafiken/Flächen", "text": "Texte", "shading": "Verläufe"}


def check_colorspaces(doc: Document) -> CheckResult:
    product = doc.product
    usage: dict = defaultdict(lambda: defaultdict(int))
    pages_by_family: dict = defaultdict(set)
    spots: set = set()
    registration_pages = []
    for info in doc.pages:
        c = info.content
        for family, kinds in c.color_usage.items():
            for kind, count in kinds.items():
                usage[family][kind] += count
            pages_by_family[family].add(info.number)
        spots |= c.spot_names
        if c.registration_used:
            registration_pages.append(info.number)

    findings: list[Finding] = []
    if "RGB" in usage:
        kinds = ", ".join(KIND_DE.get(k, k) for k in sorted(usage["RGB"]))
        findings.append(Finding(
            "color.rgb", Status.RED if product.rgb_policy == "error" else Status.YELLOW,
            f"Das PDF enthält RGB-Farben ({kinds}). Beim Druck wird in CMYK umgerechnet – "
            "leuchtende Farben können dabei matter werden.",
            data={"kinds": dict(usage["RGB"]), "pages": sorted(pages_by_family["RGB"])}))
    if spots:
        findings.append(Finding(
            "color.spot", Status.RED if product.spot_policy == "error" else Status.YELLOW,
            f"Das PDF enthält Sonderfarben ({', '.join(sorted(spots))}). Für den normalen "
            "Vierfarbdruck müssen sie in CMYK umgewandelt werden.",
            data={"spot_names": sorted(spots), "pages": sorted(pages_by_family["Spot"])}))
    if registration_pages:
        findings.append(Finding(
            "color.registration", Status.YELLOW,
            "Das PDF verwendet die Farbe \"Passermarken\" (alle Druckfarben zu 100 %). "
            "Sie ist nur für Schnitt- und Passermarken gedacht.",
            data={"pages": registration_pages}))
    for family in ("Lab", "Unknown"):
        if family in usage:
            findings.append(Finding(
                f"color.{family.lower()}", Status.YELLOW,
                "Das PDF enthält Farben in einem ungewöhnlichen Farbraum "
                f"({'Lab' if family == 'Lab' else 'nicht bestimmbar'}).",
                data={"kinds": dict(usage[family]), "pages": sorted(pages_by_family[family])}))

    families = sorted(f for f in usage if f not in ("Unknown",))
    measurements = {
        "families": families,
        "usage": {f: dict(k) for f, k in usage.items()},
        "spot_names": sorted(spots),
    }
    ok = "Alle Farben liegen in CMYK bzw. Graustufen vor." if usage else "Keine farbigen Inhalte gefunden."
    return make_result("colorspace", "Farbraum", findings, ok, measurements)


def check_tac(doc: Document, max_render_px: int = 1500) -> CheckResult:
    """Gesamtfarbauftrag über eine CMYK-Separation mit Ghostscript."""
    product = doc.product
    longest_pt = max(max(i.boxes.media.width, i.boxes.media.height) for i in doc.pages)
    dpi = max(10.0, min(150.0, max_render_px / (longest_pt / 72)))
    rendered = ghostscript_cmyk(doc.path, dpi)

    findings: list[Finding] = []
    per_page = []
    for info, arr in zip(doc.pages, rendered):
        total = print_area(info, arr, dpi, product).sum(axis=2)
        scale = info.fmt.scale if info.fmt.scale > 0 else 1.0
        px_mm = 25.4 / dpi / scale                       # Pixelkante im Endformat
        over = total > product.max_tac + 0.5
        area_cm2 = float(over.sum()) * px_mm * px_mm / 100
        max_tac = float(total.max()) if total.size else 0.0
        p99 = float(np.percentile(total, 99.9)) if total.size else 0.0
        per_page.append({"page": info.number, "max_tac": round(max_tac, 1),
                         "p999_tac": round(p99, 1), "area_over_cm2": round(area_cm2, 2)})
        if area_cm2 <= 0:
            continue
        status = Status.RED if area_cm2 >= 1.0 else Status.YELLOW
        findings.append(Finding(
            "tac.exceeded", status,
            f"Seite {info.number}: Der Farbauftrag erreicht bis zu {round(max_tac)} % "
            f"(erlaubt: {round(product.max_tac)} %) auf ca. {_fmt_area(area_cm2)}. "
            "Zu viel Farbe trocknet schlecht und kann abfärben.",
            page=info.number,
            data={"max_tac": round(max_tac, 1), "limit": product.max_tac,
                  "area_over_cm2": round(area_cm2, 2)}))
    return make_result(
        "tac", "Gesamtfarbauftrag", findings,
        f"Der Farbauftrag bleibt überall unter {round(product.max_tac)} %.",
        {"render_dpi": round(dpi, 1), "limit": product.max_tac, "pages": per_page})


def print_area(info, arr: np.ndarray, dpi: float, product) -> np.ndarray:
    """Schneidet das Ghostscript-Bild (MediaBox, ggf. gedreht) auf den gedruckten Bereich
    zu: Endformat plus geforderter Beschnitt. Was außerhalb liegt (z. B. Schnittmarken),
    wird abgeschnitten und zählt nicht."""
    rot = info.boxes.rotate
    if rot:
        arr = np.rot90(arr, k=rot // 90)   # Ghostscript dreht im Uhrzeigersinn → zurückdrehen
    media = info.boxes.media
    if info.fmt.ok:
        b = pt(product.bleed_mm * info.fmt.scale)
        t = info.fmt.trim
        region = Box(t.x0 - b, t.y0 - b, t.x1 + b, t.y1 + b)
    else:
        region = info.boxes.bleed if info.boxes.has_bleed else info.boxes.crop
    region = region.intersect(media) or media
    h, w = arr.shape[:2]
    sx, sy = w / media.width, h / media.height
    c0 = int(np.floor((region.x0 - media.x0) * sx))
    c1 = int(np.ceil((region.x1 - media.x0) * sx))
    r0 = int(np.floor((media.y1 - region.y1) * sy))
    r1 = int(np.ceil((media.y1 - region.y0) * sy))
    return arr[max(r0, 0):min(r1, h), max(c0, 0):min(c1, w)]


def _fmt_area(cm2: float) -> str:
    if cm2 >= 100:
        return f"{cm2 / 10000:.2f} m²".replace(".", ",")
    return f"{cm2:.1f} cm²".replace(".", ",")

