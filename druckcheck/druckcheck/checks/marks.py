"""Prüfungen: Haarlinien, Schnittmarken im Dokument."""

from __future__ import annotations

from ..document import Document, PageInfo
from ..models import CheckResult, Finding, Status, make_result
from ..pdfdata import Box, StrokeEvent, mm

MARK_MIN_MM = 2.0          # typische Schnittmarken sind 3–10 mm lang
MARK_MAX_MM = 25.0
ALIGN_TOL_MM = 0.75        # Marke liegt in Verlängerung der Endformatkante
CORNER_ZONE_MM = 20.0
MIN_MARK_SEGMENTS = 4


def _crop_mark_segments(info: PageInfo) -> list[tuple[StrokeEvent, tuple]]:
    """Gerade, kurze, achsparallele Linien außerhalb des Endformats in Verlängerung
    der Endformatkanten (bzw. ohne erkanntes Endformat: in den Seitenecken)."""
    trim = info.fmt.trim
    media = info.boxes.media
    found = []
    for stroke in info.content.strokes:
        if not stroke.segments:
            continue
        for (x0, y0), (x1, y1) in stroke.segments:
            horizontal = abs(y0 - y1) < 0.01
            vertical = abs(x0 - x1) < 0.01
            if not (horizontal or vertical):
                continue
            length = mm(abs(x1 - x0) + abs(y1 - y0))
            if not MARK_MIN_MM <= length <= MARK_MAX_MM:
                continue
            seg_box = Box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            if trim is not None:
                inside = (seg_box.x0 > trim.x0 + 0.1 and seg_box.x1 < trim.x1 - 0.1
                          and seg_box.y0 > trim.y0 + 0.1 and seg_box.y1 < trim.y1 - 0.1)
                if inside:
                    continue
                if horizontal:
                    aligned = min(abs(mm(y0 - trim.y0)), abs(mm(y0 - trim.y1))) <= ALIGN_TOL_MM
                    outside = seg_box.x1 <= trim.x0 + 0.1 or seg_box.x0 >= trim.x1 - 0.1
                else:
                    aligned = min(abs(mm(x0 - trim.x0)), abs(mm(x0 - trim.x1))) <= ALIGN_TOL_MM
                    outside = seg_box.y1 <= trim.y0 + 0.1 or seg_box.y0 >= trim.y1 - 0.1
                if aligned and outside:
                    found.append((stroke, (x0, y0, x1, y1)))
            else:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                near_x = min(mm(cx - media.x0), mm(media.x1 - cx)) <= CORNER_ZONE_MM
                near_y = min(mm(cy - media.y0), mm(media.y1 - cy)) <= CORNER_ZONE_MM
                if near_x and near_y:
                    found.append((stroke, (x0, y0, x1, y1)))
    return found


def check_crop_marks(doc: Document) -> CheckResult:
    findings: list[Finding] = []
    for info in doc.pages:
        segments = _crop_mark_segments(info)
        registration = any(s.colorspace.registration for s, _ in segments)
        needed = MIN_MARK_SEGMENTS if info.fmt.trim is not None else 2 * MIN_MARK_SEGMENTS
        if len(segments) < needed and not (registration and len(segments) >= 2):
            continue
        bleed_outer = info.boxes.bleed
        outside_bleed = info.boxes.has_trim and info.boxes.has_bleed and all(
            not Box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)).intersects(bleed_outer)
            for _, (x0, y0, x1, y1) in segments)
        data = {"segments": len(segments), "registration_color": registration,
                "outside_bleed_box": outside_bleed}
        if outside_bleed:
            findings.append(Finding(
                "marks.crop_marks_outside", Status.YELLOW,
                f"Seite {info.number} enthält Schnittmarken außerhalb des Beschnitts. "
                "Viele Druckereien möchten Dateien ohne Marken – sie setzen eigene.",
                page=info.number, data=data))
        else:
            findings.append(Finding(
                "marks.crop_marks", Status.RED,
                f"Seite {info.number} enthält Schnittmarken. Bitte ohne Schnittmarken exportieren "
                "(nur mit Beschnitt), sonst können die Marken mitgedruckt werden.",
                page=info.number, data=data))
    return make_result("crop_marks", "Schnittmarken", findings, "Keine Schnittmarken im Dokument.")


def check_hairlines(doc: Document) -> CheckResult:
    product = doc.product
    findings: list[Finding] = []
    stats = []
    for info in doc.pages:
        trim = info.fmt.trim or info.boxes.crop
        scale = info.fmt.scale if info.fmt.scale > 0 else 1.0
        mark_strokes = {id(s) for s, _ in _crop_mark_segments(info)}
        thin = []
        for stroke in info.content.strokes:
            if id(stroke) in mark_strokes:
                continue
            bbox = stroke.bbox
            # Linien, die nur im Beschnitt liegen, werden abgeschnitten
            grown = Box(bbox.x0 - 0.01, bbox.y0 - 0.01, bbox.x1 + 0.01, bbox.y1 + 0.01)
            if not grown.intersects(trim):
                continue
            final_width = stroke.width_pt / scale
            if final_width < product.hairline_pt - 1e-6:
                thin.append(final_width)
        if not thin:
            continue
        thinnest = min(thin)
        stats.append({"page": info.number, "count": len(thin), "thinnest_pt": round(thinnest, 3)})
        status = Status.RED if thinnest <= product.hairline_red_pt + 1e-6 else Status.YELLOW
        width_txt = "0 pt (\"dünnstmöglich\")" if thinnest < 1e-6 else _pt(thinnest)
        findings.append(Finding(
            "lines.hairline", status,
            f"Seite {info.number}: {'1 Linie ist' if len(thin) == 1 else f'{len(thin)} Linien sind'} "
            f"dünner als {_pt(product.hairline_pt)} "
            f"(dünnste: {width_txt}). Solche Haarlinien können im Druck wegbrechen oder verschwinden.",
            page=info.number, data={"count": len(thin), "thinnest_pt": round(thinnest, 3),
                                    "limit_pt": product.hairline_pt}))
    return make_result("hairlines", "Haarlinien", findings,
                       f"Keine Linien dünner als {_pt(product.hairline_pt)}.",
                       {"pages": stats})


def _pt(v: float) -> str:
    return f"{v:.2f} pt".replace(".", ",")
