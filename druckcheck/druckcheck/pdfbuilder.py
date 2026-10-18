"""Kleiner PDF-Baukasten für Test- und Beispiel-PDFs.

Erzeugt PDFs mit exakt kontrollierten Eigenschaften (Boxen, Farbräume, Bildauflösung,
eingebettete/nicht eingebettete Schriften, Transparenz, Überdrucken, Schnittmarken).
Alle Koordinaten in mm, Ursprung unten links auf der MediaBox.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pikepdf
import pymupdf

PT = 72 / 25.4


def _n(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def _color_ops(cmyk=None, rgb=None, gray=None, spot=None, stroke=False) -> str:
    if spot is not None:
        name, tint = spot
        return f"/{name} {'CS' if stroke else 'cs'} {_n(tint)} {'SCN' if stroke else 'scn'}"
    if cmyk is not None:
        return " ".join(_n(v) for v in cmyk) + (" K" if stroke else " k")
    if rgb is not None:
        return " ".join(_n(v) for v in rgb) + (" RG" if stroke else " rg")
    if gray is not None:
        return f"{_n(gray)} {'G' if stroke else 'g'}"
    return ""


_EMBEDDED_FONT_CACHE: dict = {}


def _embedded_font(pdf: pikepdf.Pdf) -> pikepdf.Object:
    """Nimbus Sans (Helvetica-Klon aus PyMuPDF) als eingebettete Type1C-Schrift."""
    if id(pdf) in _EMBEDDED_FONT_CACHE:
        return _EMBEDDED_FONT_CACHE[id(pdf)]
    font = pymupdf.Font("helv")
    widths = [int(round(font.glyph_advance(c) * 1000)) for c in range(32, 256)]
    fontfile = pikepdf.Stream(pdf, zlib.compress(font.buffer))
    fontfile["/Filter"] = pikepdf.Name.FlateDecode
    fontfile["/Subtype"] = pikepdf.Name.Type1C
    descriptor = pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor, FontName=pikepdf.Name("/NimbusSans-Regular"),
        Flags=32, FontBBox=[-200, -300, 1100, 1000], ItalicAngle=0, Ascent=718,
        Descent=-207, CapHeight=718, StemV=88, FontFile3=fontfile)
    obj = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
        BaseFont=pikepdf.Name("/NimbusSans-Regular"), FirstChar=32, LastChar=255,
        Widths=widths, Encoding=pikepdf.Name.WinAnsiEncoding,
        FontDescriptor=pdf.make_indirect(descriptor)))
    _EMBEDDED_FONT_CACHE[id(pdf)] = obj
    return obj


@dataclass
class PageBuilder:
    pdf: pikepdf.Pdf
    width_mm: float
    height_mm: float
    ops: list[str] = field(default_factory=list)
    fonts: dict = field(default_factory=dict)
    xobjects: dict = field(default_factory=dict)
    extgstates: dict = field(default_factory=dict)
    colorspaces: dict = field(default_factory=dict)
    boxes: dict = field(default_factory=dict)
    rotate: int = 0

    # -- Boxen --------------------------------------------------------------
    def set_box(self, name: str, x0, y0, x1, y1) -> "PageBuilder":
        self.boxes[name] = [x0 * PT, y0 * PT, x1 * PT, y1 * PT]
        return self

    def set_trim_with_bleed(self, bleed_mm: float, bleedbox: bool = True) -> "PageBuilder":
        """MediaBox = Endformat + Beschnitt; setzt TrimBox (und BleedBox)."""
        b = bleed_mm
        self.set_box("/TrimBox", b, b, self.width_mm - b, self.height_mm - b)
        if bleedbox:
            self.set_box("/BleedBox", 0, 0, self.width_mm, self.height_mm)
        return self

    # -- Zeichnen -----------------------------------------------------------
    def raw(self, ops: str) -> "PageBuilder":
        self.ops.append(ops)
        return self

    def rect(self, x, y, w, h, *, cmyk=None, rgb=None, gray=None, spot=None, gs=None) -> "PageBuilder":
        c = _color_ops(cmyk, rgb, gray, spot)
        g = f"/{gs} gs " if gs else ""
        self.ops.append(f"q {g}{c} {_n(x * PT)} {_n(y * PT)} {_n(w * PT)} {_n(h * PT)} re f Q")
        return self

    def line(self, x0, y0, x1, y1, *, width_pt: float, cmyk=(0, 0, 0, 1), rgb=None,
             spot=None, gs=None) -> "PageBuilder":
        c = _color_ops(None if rgb or spot else cmyk, rgb, None, spot, stroke=True)
        g = f"/{gs} gs " if gs else ""
        self.ops.append(f"q {g}{c} {_n(width_pt)} w {_n(x0 * PT)} {_n(y0 * PT)} m "
                        f"{_n(x1 * PT)} {_n(y1 * PT)} l S Q")
        return self

    def text(self, x, y, s: str, *, size_pt: float = 12, embedded: bool = True,
             cmyk=(0, 0, 0, 1), rgb=None, gs=None) -> "PageBuilder":
        if embedded:
            name = "FE"
            self.fonts[name] = _embedded_font(self.pdf)
        else:
            name = "FH"
            self.fonts[name] = pikepdf.Dictionary(
                Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica, Encoding=pikepdf.Name.WinAnsiEncoding)
        c = _color_ops(None if rgb else cmyk, rgb)
        g = f"/{gs} gs " if gs else ""
        escaped = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.ops.append(f"q {g}{c} BT /{name} {_n(size_pt)} Tf {_n(x * PT)} {_n(y * PT)} Td "
                        f"({escaped}) Tj ET Q")
        return self

    def image(self, x, y, w, h, *, px: tuple[int, int], mode: str = "CMYK",
              smask: bool = False, pattern: str = "gradient", gs=None) -> "PageBuilder":
        name = f"Im{len(self.xobjects) + 1}"
        self.xobjects[name] = make_image(self.pdf, px[0], px[1], mode, smask, pattern)
        g = f"/{gs} gs " if gs else ""
        self.ops.append(f"q {g}{_n(w * PT)} 0 0 {_n(h * PT)} {_n(x * PT)} {_n(y * PT)} cm /{name} Do Q")
        return self

    def extgstate(self, name: str, **entries) -> "PageBuilder":
        d = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState)
        for k, v in entries.items():
            d[f"/{k}"] = pikepdf.Name(v) if isinstance(v, str) else v
        self.extgstates[name] = d
        return self

    def spot_color(self, name: str, colorant: str, cmyk_alt=(0, 0, 0, 1)) -> "PageBuilder":
        c, m, y, k = cmyk_alt
        fn = pikepdf.Dictionary(FunctionType=2, Domain=[0, 1], C0=[0, 0, 0, 0], C1=[c, m, y, k], N=1)
        self.colorspaces[name] = pikepdf.Array([
            pikepdf.Name.Separation, pikepdf.Name("/" + colorant), pikepdf.Name.DeviceCMYK, fn])
        return self

    def crop_marks(self, trim: tuple[float, float, float, float], *, offset_mm=3.0,
                   length_mm=5.0, width_pt=0.25, registration=True) -> "PageBuilder":
        """Klassische Eck-Schnittmarken außerhalb des Endformats."""
        x0, y0, x1, y1 = trim
        spot = None
        if registration:
            self.spot_color("CSAll", "All")
            spot = ("CSAll", 1)
        o, ln = offset_mm, length_mm
        for x, sx in ((x0, -1), (x1, 1)):
            for y, sy in ((y0, -1), (y1, 1)):
                # horizontale Marke in Verlängerung der Kante y, vertikale in Verlängerung von x
                self.line(x + sx * o, y, x + sx * (o + ln), y, width_pt=width_pt, spot=spot)
                self.line(x, y + sy * o, x, y + sy * (o + ln), width_pt=width_pt, spot=spot)
        return self

    # -- Ausgabe ------------------------------------------------------------
    def build(self) -> None:
        page = self.pdf.add_blank_page(page_size=(self.width_mm * PT, self.height_mm * PT))
        page.obj["/Contents"] = self.pdf.make_stream("\n".join(self.ops).encode("latin-1"))
        res = pikepdf.Dictionary()
        if self.fonts:
            res["/Font"] = pikepdf.Dictionary({f"/{k}": v for k, v in self.fonts.items()})
        if self.xobjects:
            res["/XObject"] = pikepdf.Dictionary({f"/{k}": v for k, v in self.xobjects.items()})
        if self.extgstates:
            res["/ExtGState"] = pikepdf.Dictionary({f"/{k}": v for k, v in self.extgstates.items()})
        if self.colorspaces:
            res["/ColorSpace"] = pikepdf.Dictionary({f"/{k}": v for k, v in self.colorspaces.items()})
        page.obj["/Resources"] = res
        for name, box in self.boxes.items():
            page.obj[name] = pikepdf.Array(box)
        if self.rotate:
            page.obj["/Rotate"] = self.rotate


def make_image(pdf: pikepdf.Pdf, w: int, h: int, mode: str = "CMYK", smask: bool = False,
               pattern: str = "gradient") -> pikepdf.Stream:
    channels = {"CMYK": 4, "RGB": 3, "L": 1}[mode]
    yy, xx = np.mgrid[0:h, 0:w]
    if pattern == "dark":   # sehr dunkles Bild (hoher Farbauftrag in CMYK)
        data = np.full((h, w, channels), 255 if mode == "CMYK" else 10, dtype=np.uint8)
    else:
        base = ((xx * 255) // max(w - 1, 1)).astype(np.uint8)
        other = ((yy * 255) // max(h - 1, 1)).astype(np.uint8)
        layers = [base, other, (255 - base), (other // 4)][:channels]
        data = np.stack(layers, axis=2).astype(np.uint8)
    stream = pikepdf.Stream(pdf, zlib.compress(data.tobytes()))
    stream["/Type"] = pikepdf.Name.XObject
    stream["/Subtype"] = pikepdf.Name.Image
    stream["/Width"] = w
    stream["/Height"] = h
    stream["/BitsPerComponent"] = 8
    stream["/ColorSpace"] = pikepdf.Name({"CMYK": "/DeviceCMYK", "RGB": "/DeviceRGB", "L": "/DeviceGray"}[mode])
    stream["/Filter"] = pikepdf.Name.FlateDecode
    if smask:
        alpha = np.full((h, w), 128, dtype=np.uint8)
        sm = pikepdf.Stream(pdf, zlib.compress(alpha.tobytes()))
        sm["/Type"] = pikepdf.Name.XObject
        sm["/Subtype"] = pikepdf.Name.Image
        sm["/Width"] = w
        sm["/Height"] = h
        sm["/BitsPerComponent"] = 8
        sm["/ColorSpace"] = pikepdf.Name.DeviceGray
        sm["/Filter"] = pikepdf.Name.FlateDecode
        stream["/SMask"] = sm
    return stream


class PdfBuilder:
    def __init__(self) -> None:
        self.pdf = pikepdf.new()
        self.pages: list[PageBuilder] = []

    def page(self, width_mm: float, height_mm: float) -> PageBuilder:
        pb = PageBuilder(self.pdf, width_mm, height_mm)
        self.pages.append(pb)
        return pb

    def save(self, path: str | Path) -> Path:
        for pb in self.pages:
            pb.build()
        path = Path(path)
        self.pdf.save(path)
        _EMBEDDED_FONT_CACHE.pop(id(self.pdf), None)
        return path
