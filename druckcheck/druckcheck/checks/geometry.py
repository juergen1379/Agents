"""Prüfung: Seitenformat, Maßstab, Beschnittzugabe und ob das Motiv in den Beschnitt läuft."""

from __future__ import annotations

import numpy as np

from ..document import Document, PageInfo
from ..formats import find_matching_products
from ..models import CheckResult, Finding, Status, make_result
from ..pdfdata import Box, pt
from ..products import load_products
from ..render import render_rgb

CHECK_ID = "geometry"
TITLE = "Format & Beschnitt"

WHITE_LEVEL = 250          # RGB-Wert ab dem ein Pixel als "weiß / unbedruckt" gilt
EDGE_YELLOW = 0.05         # Anteil einer Kante, ab dem "Motiv endet am Rand" gelb wird
EDGE_RED = 0.25            # ... und rot


def check_geometry(doc: Document) -> CheckResult:
    product = doc.product
    findings: list[Finding] = []
    measurements: dict = {"pages": []}

    if doc.page_count > product.max_pages:
        findings.append(Finding(
            "geometry.too_many_pages", Status.RED,
            f"Das PDF hat {doc.page_count} Seiten, für {product.name} sind höchstens "
            f"{product.max_pages} vorgesehen.",
            data={"page_count": doc.page_count, "max_pages": product.max_pages}))

    sizes = set()
    for info in doc.pages:
        fmt = info.fmt
        sizes.add(tuple(round(v) for v in fmt.page_size_mm))
        measurements["pages"].append({
            "page": info.number,
            "page_size_mm": fmt.page_size_mm,
            "trim_mm": info.boxes.trim.as_mm() if info.boxes.has_trim else None,
            "format_ok": fmt.ok,
            "scale": round(fmt.scale, 4),
            "source": fmt.source,
            "bleed_final_mm": {k: round(v, 2) for k, v in fmt.bleed_final_mm.items()},
        })
        findings.extend(_page_format_findings(info, doc))
        if fmt.ok and product.bleed_mm > 0 and fmt.min_bleed_final_mm >= product.bleed_mm - product.tolerance_mm:
            findings.extend(_bleed_content_findings(info, doc))

    if len(sizes) > 1:
        findings.append(Finding(
            "geometry.mixed_page_sizes", Status.YELLOW,
            "Die Seiten des PDFs haben unterschiedliche Größen.",
            data={"sizes_mm": sorted(sizes)}))

    return make_result(CHECK_ID, TITLE, findings,
                       f"Format und Beschnitt passen zu {product.name}.", measurements)


def _page_format_findings(info: PageInfo, doc: Document) -> list[Finding]:
    product, fmt, n = doc.product, info.fmt, info.number
    out: list[Finding] = []
    tw, th = product.trim_mm

    if not fmt.ok:
        w, h = fmt.page_size_mm
        matches = find_matching_products(w, h, load_products(), product.tolerance_mm)
        hint = f" Das passt eher zu: {', '.join(matches)}." if matches else ""
        out.append(Finding(
            "geometry.wrong_format", Status.RED,
            f"Seite {n} ist {_fmt_mm(w)} × {_fmt_mm(h)} mm groß – erwartet wird "
            f"{_fmt_mm(tw)} × {_fmt_mm(th)} mm Endformat"
            + (f" plus {_fmt_mm(product.bleed_mm)} mm Beschnitt je Seite" if product.bleed_mm else "")
            + _scale_hint(product) + "." + hint,
            page=n, data={"page_size_mm": [w, h], "expected_trim_mm": [tw, th],
                          "expected_bleed_mm": product.bleed_mm, "matches": matches}))
        return out

    if not fmt.scale_allowed:
        w, h = fmt.page_size_mm
        matches = [m for m in find_matching_products(w, h, load_products(), product.tolerance_mm)
                   if m != product.name]
        hint = f" Die Seitengröße passt eher zu: {', '.join(matches)}." if matches else ""
        out.append(Finding(
            "geometry.scaled", Status.RED,
            f"Seite {n} hat zwar das richtige Seitenverhältnis, ist aber im Maßstab "
            f"{_fmt_scale(fmt.scale)} statt im Endformat {_fmt_mm(tw)} × {_fmt_mm(th)} mm angelegt."
            + hint + " Bitte im Endformat anlegen oder das passende Produkt wählen.",
            page=n, data={"scale": fmt.scale, "matches": matches}))
    elif abs(fmt.scale - 1) > 1e-6:
        out.append(Finding(
            "geometry.scale_info", Status.GREEN,
            f"Seite {n} ist im zulässigen Maßstab {_fmt_scale(fmt.scale)} angelegt.",
            page=n, data={"scale": fmt.scale}))

    if product.bleed_mm > 0:
        avail = fmt.min_bleed_final_mm
        data = {"required_mm": product.bleed_mm, "available_mm": round(avail, 2),
                "sides_mm": {k: round(v, 2) for k, v in fmt.bleed_final_mm.items()}}
        if avail <= product.tolerance_mm:
            out.append(Finding(
                "geometry.no_bleed", Status.RED,
                f"Seite {n} hat keinen Beschnitt. Benötigt werden {_fmt_mm(product.bleed_mm)} mm "
                "rundum, sonst können weiße Ränder (\"Blitzer\") entstehen.",
                page=n, data=data))
        elif avail < product.bleed_mm - product.tolerance_mm:
            out.append(Finding(
                "geometry.too_little_bleed", Status.YELLOW,
                f"Seite {n} hat nur {_fmt_mm(avail)} mm Beschnitt, benötigt werden "
                f"{_fmt_mm(product.bleed_mm)} mm.",
                page=n, data=data))
        else:
            out.append(Finding(
                "geometry.bleed_ok", Status.GREEN,
                f"Seite {n}: Beschnitt vorhanden ({_fmt_mm(avail)} mm).", page=n, data=data))
    return out


def _bleed_content_findings(info: PageInfo, doc: Document) -> list[Finding]:
    """Rendert die Seite und prüft je Kante, ob farbige Flächen am Endformatrand
    im Beschnitt weiß werden (Hintergrund nicht in den Beschnitt gezogen)."""
    product, fmt = doc.product, info.fmt
    trim = fmt.trim
    bleed_pt = pt(product.bleed_mm * fmt.scale)
    outer = Box(trim.x0 - bleed_pt, trim.y0 - bleed_pt, trim.x1 + bleed_pt, trim.y1 + bleed_pt)
    region = outer.intersect(info.boxes.media)
    if region is None:
        return []
    # Ziel: der Beschnittstreifen soll mindestens ~6 Pixel breit sein
    dpi = min(300.0, max(36.0, 6 * 72 / bleed_pt))
    img = render_rgb(doc.fitz_page(info.number), region, dpi)
    h, w = img.shape[:2]
    sx, sy = w / region.width, h / region.height
    nonwhite = (img < WHITE_LEVEL).any(axis=2)

    def col(x_pt):
        return int(np.clip((x_pt - region.x0) * sx, 0, w - 1))

    def row(y_pt):  # Bildzeilen laufen von oben nach unten
        return int(np.clip((region.y1 - y_pt) * sy, 0, h - 1))

    inset = 1.5 / sx                 # ca. 1,5 Pixel innerhalb des Endformats
    outset = 1.5 / sx                # ca. 1,5 Pixel innerhalb der äußeren Beschnittkante
    if (bleed_pt - outset) * sx < 1.5:
        return []                    # Beschnittstreifen zu schmal zum Auswerten
    r0, r1 = row(trim.y1), row(trim.y0)
    c0, c1 = col(trim.x0), col(trim.x1)
    edges = {
        "top": (nonwhite[row(trim.y1 - inset), c0:c1], nonwhite[row(outer.y1 - outset), c0:c1]),
        "bottom": (nonwhite[row(trim.y0 + inset), c0:c1], nonwhite[row(outer.y0 + outset), c0:c1]),
        "left": (nonwhite[r0:r1, col(trim.x0 + inset)], nonwhite[r0:r1, col(outer.x0 + outset)]),
        "right": (nonwhite[r0:r1, col(trim.x1 - inset)], nonwhite[r0:r1, col(outer.x1 - outset)]),
    }
    fractions = {}
    for side, (inner, outer_line) in edges.items():
        if inner.size == 0:
            continue
        fractions[side] = float((inner & ~outer_line).sum()) / inner.size
    if not fractions:
        return []
    worst_side = max(fractions, key=fractions.get)
    worst = fractions[worst_side]
    if worst < EDGE_YELLOW:
        return []
    status = Status.RED if worst >= EDGE_RED else Status.YELLOW
    sides_de = {"top": "oben", "bottom": "unten", "left": "links", "right": "rechts"}
    affected = [sides_de[s] for s, f in fractions.items() if f >= EDGE_YELLOW]
    return [Finding(
        "geometry.bleed_not_filled", status,
        f"Seite {info.number}: Der Beschnitt ist zwar angelegt, aber das Motiv reicht "
        f"nicht hinein ({', '.join(affected)}). Am Schnittrand können weiße Blitzer entstehen.",
        page=info.number, data={"fraction_per_side": {k: round(v, 3) for k, v in fractions.items()}})]


def _fmt_mm(v: float) -> str:
    s = f"{v:.1f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def _scale_hint(product) -> str:
    others = [s for s in product.allowed_scales if abs(s - 1) > 1e-6]
    if not others:
        return ""
    tw, th = product.trim_mm
    parts = [f"im Maßstab {_fmt_scale(s)}: {_fmt_mm(tw * s)} × {_fmt_mm(th * s)} mm" for s in others]
    return " (oder " + " bzw. ".join(parts) + ")"


def _fmt_scale(scale: float) -> str:
    if scale >= 1:
        return f"{_fmt_mm(scale)}:1"
    return f"1:{_fmt_mm(1 / scale)}"
