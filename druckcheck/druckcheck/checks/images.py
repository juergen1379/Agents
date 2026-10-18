"""Prüfung: effektive Bildauflösung im Endformat."""

from __future__ import annotations

from ..document import Document
from ..models import CheckResult, Finding, Status, make_result
from ..pdfdata import mm

MIN_PIXELS = 16            # Platzhalter-/Abstandsbilder ignorieren
MIN_AREA_MM2 = 25          # winzige Bildchen (< 5 × 5 mm im Endformat) ignorieren


def check_image_resolution(doc: Document) -> CheckResult:
    product = doc.product
    findings: list[Finding] = []
    evaluated = []
    for info in doc.pages:
        scale = info.fmt.scale if info.fmt.scale > 0 else 1.0
        visible_area = info.boxes.bleed if info.boxes.has_bleed else info.boxes.crop
        for img in info.content.images:
            if img.is_mask or img.width_px * img.height_px < MIN_PIXELS:
                continue
            visible = img.bbox.intersect(visible_area)
            if visible is None:
                continue
            w_mm, h_mm = mm(img.bbox.width) / scale, mm(img.bbox.height) / scale
            if w_mm * h_mm < MIN_AREA_MM2:
                continue
            dpi = img.ppi * scale    # Auflösung bezogen auf das fertige Produkt
            entry = {
                "page": info.number, "name": img.name,
                "pixels": [img.width_px, img.height_px],
                "size_mm": [round(w_mm, 1), round(h_mm, 1)],
                "dpi": round(dpi, 1),
                "estimated": not info.fmt.ok,   # Format unklar → Maßstab nur geschätzt
            }
            evaluated.append(entry)
            if round(dpi) < product.min_dpi:
                status = Status.RED
            elif round(dpi) < product.target_dpi:
                status = Status.YELLOW
            else:
                continue
            findings.append(Finding(
                "images.low_resolution", status,
                f"Seite {info.number}: Ein Bild ({img.width_px} × {img.height_px} Pixel, "
                f"{_cm(w_mm)} × {_cm(h_mm)} cm groß) hat nur {round(dpi)} dpi. "
                f"Für {product.name} sind mindestens {round(product.min_dpi)} dpi nötig, "
                f"ideal {round(product.target_dpi)} dpi."
                + (" (Geschätzt, weil das Format nicht passt.)" if not info.fmt.ok else ""),
                page=info.number, data={**entry, "min_dpi": product.min_dpi,
                                        "target_dpi": product.target_dpi}))
    measurements = {
        "images": evaluated,
        "min_dpi_found": min((e["dpi"] for e in evaluated), default=None),
        "required": {"min_dpi": product.min_dpi, "target_dpi": product.target_dpi},
    }
    if not evaluated:
        ok = "Keine Bilder im Dokument."
    elif len(evaluated) == 1:
        ok = f"Das Bild hat genug Auflösung (≥ {round(product.target_dpi)} dpi)."
    else:
        ok = f"Alle {len(evaluated)} Bilder haben genug Auflösung (≥ {round(product.target_dpi)} dpi)."
    return make_result("images", "Bildauflösung", findings, ok, measurements)


def _cm(v_mm: float) -> str:
    return f"{v_mm / 10:.1f}".replace(".", ",")
