"""Formaterkennung: Welche Fläche der Seite ist das Endformat, in welchem Maßstab,
und wie viel Beschnitt ist geometrisch vorhanden?

Alle Werte in FormatMatch, die auf "_final_mm" enden, beziehen sich auf das fertige
Produkt (also bei 1:10-Daten bereits hochgerechnet).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .pdfdata import Box, PageBoxes, mm, pt
from .products import Product

PROPORTION_TOLERANCE = 0.01   # 1 % Abweichung im Seitenverhältnis gilt als proportional


@dataclass
class FormatMatch:
    ok: bool                         # Endformat (ggf. skaliert) erkannt
    trim: Box | None                 # Endformat in Seitenkoordinaten
    scale: float                     # Seite / Endformat (1.0 = 1:1, 0.1 = 1:10)
    scale_allowed: bool              # Maßstab in allowed_scales
    source: str                      # "trimbox" | "mediabox" | "none"
    landscape: bool = False
    bleed_final_mm: dict = field(default_factory=dict)   # top/right/bottom/left
    page_size_mm: tuple[float, float] = (0.0, 0.0)       # sichtbare Seitengröße
    note: str = ""

    @property
    def min_bleed_final_mm(self) -> float:
        return min(self.bleed_final_mm.values()) if self.bleed_final_mm else 0.0


def _orientations(product: Product):
    w, h = product.trim_mm
    yield w, h, w > h
    if abs(w - h) > 1e-6:
        yield h, w, h > w


def _bleed_sides(trim: Box, outer: Box, scale: float) -> dict:
    return {
        "top": max(0.0, mm(outer.y1 - trim.y1) / scale),
        "right": max(0.0, mm(outer.x1 - trim.x1) / scale),
        "bottom": max(0.0, mm(trim.y0 - outer.y0) / scale),
        "left": max(0.0, mm(trim.x0 - outer.x0) / scale),
    }


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def _centered(outer: Box, w_mm: float, h_mm: float) -> Box:
    cx, cy = (outer.x0 + outer.x1) / 2, (outer.y0 + outer.y1) / 2
    return Box(cx - pt(w_mm) / 2, cy - pt(h_mm) / 2, cx + pt(w_mm) / 2, cy + pt(h_mm) / 2)


def resolve_format(boxes: PageBoxes, product: Product) -> FormatMatch:
    tol = product.tolerance_mm
    outer = boxes.bleed if boxes.has_bleed else boxes.crop
    page_size = (round(mm(boxes.crop.width), 2), round(mm(boxes.crop.height), 2))

    if boxes.has_trim:
        tw, th = mm(boxes.trim.width), mm(boxes.trim.height)
        match = _match_size(tw, th, product, tol)
        if match is None:
            return FormatMatch(False, None, _estimate_scale(tw, th, product), False, "trimbox",
                               page_size_mm=(round(tw, 2), round(th, 2)),
                               note="TrimBox passt nicht zum Endformat")
        scale, allowed, landscape = match
        return FormatMatch(True, boxes.trim, scale, allowed, "trimbox", landscape,
                           _bleed_sides(boxes.trim, outer, scale), page_size)

    # Keine TrimBox: Endformat muss aus der Seitengröße abgeleitet werden.
    ow, oh = mm(outer.width), mm(outer.height)
    candidates = []
    for w, h, landscape in _orientations(product):
        for scale in product.allowed_scales:
            ew, eh = w * scale, h * scale
            bx, by = (ow - ew) / 2, (oh - eh) / 2
            if bx < -tol / 2 or by < -tol / 2:
                continue
            # Beschnitt muss rundum gleich sein (Endformat mittig) ...
            if not _close(bx, by, tol):
                continue
            # ... und darf nicht unplausibel groß sein (sonst falsches Format)
            max_margin = max(product.bleed_mm, 3.0) * scale + 25 * scale + tol
            if bx > max_margin:
                continue
            candidates.append((bx, scale, True, landscape, ew, eh))
        # proportional, aber nicht zugelassener Maßstab: mit und ohne Beschnitt
        for with_bleed in (False, True):
            b = product.bleed_mm if with_bleed else 0.0
            scale = ow / (w + 2 * b)
            if scale <= 0:
                continue
            if abs(oh - (h + 2 * b) * scale) <= max(tol, PROPORTION_TOLERANCE * oh):
                if not any(_close(scale, s, 1e-3) for s in product.allowed_scales):
                    candidates.append((b * scale, scale, False, landscape, w * scale, h * scale))

    if not candidates:
        return FormatMatch(False, None, _estimate_scale(ow, oh, product), False, "none",
                           page_size_mm=page_size, note="Seitengröße passt nicht zum Endformat")
    # zugelassene Maßstäbe bevorzugen, dann den kleinsten Rand
    bx, scale, allowed, landscape, ew, eh = sorted(
        candidates, key=lambda c: (not c[2], abs(c[0])))[0]
    trim = _centered(outer, ew, eh)
    return FormatMatch(True, trim, scale, allowed, "mediabox", landscape,
                       _bleed_sides(trim, outer, scale), page_size,
                       note="Endformat aus Seitengröße abgeleitet (keine TrimBox)")


def _match_size(w_mm: float, h_mm: float, product: Product, tol: float):
    """Prüft, ob w×h dem Endformat in einem (zugelassenen oder proportionalen) Maßstab entspricht."""
    best = None
    for w, h, landscape in _orientations(product):
        for scale in product.allowed_scales:
            if _close(w_mm, w * scale, tol) and _close(h_mm, h * scale, tol):
                return scale, True, landscape
        scale = w_mm / w
        if abs(h_mm - h * scale) <= max(tol, PROPORTION_TOLERANCE * h_mm):
            best = (scale, False, landscape)
    return best


def _estimate_scale(w_mm: float, h_mm: float, product: Product) -> float:
    pw, ph = product.trim_mm
    return max(((w_mm * h_mm) / (pw * ph)) ** 0.5, 1e-6)


def find_matching_products(w_mm: float, h_mm: float, products: dict, tol: float = 0.5) -> list[str]:
    """Hilfreich für Fehlermeldungen: Zu welchem Produkt passt diese Seitengröße?"""
    names = []
    for p in products.values():
        for w, h, _ in _orientations(p):
            for scale in p.allowed_scales:
                for b in (0.0, p.bleed_mm):
                    if (_close(w_mm, (w + 2 * b) * scale, tol)
                            and _close(h_mm, (h + 2 * b) * scale, tol)):
                        if p.name not in names:
                            names.append(p.name)
    return names
