"""Auswertung der PDF-Inhalte ohne Rendering.

Ein kleiner Content-Stream-Interpreter auf Basis von pikepdf verfolgt Grafikzustand
(CTM, Farbräume, Linienstärke, ExtGState) und sammelt pro Seite alles, was die
einzelnen Prüfungen brauchen: Bildplatzierungen, Farbverwendung, Konturen,
verwendete Schriften, Transparenz- und Überdruck-Merkmale.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import pikepdf

PT_PER_MM = 72 / 25.4
MM_PER_PT = 25.4 / 72

PROCESS_NAMES = {"Cyan", "Magenta", "Yellow", "Black"}
MAX_DEPTH = 12          # Verschachtelungstiefe Form-XObjects/Muster
MAX_OPERATIONS = 3_000_000


def mm(pt: float) -> float:
    return pt * MM_PER_PT


def pt(mm_value: float) -> float:
    return mm_value * PT_PER_MM


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    """Rechteck in PDF-Koordinaten (Punkt, Ursprung unten links)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_array(cls, arr) -> "Box":
        x0, y0, x1, y1 = (float(v) for v in arr)
        return cls(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    @classmethod
    def from_points(cls, points) -> "Box":
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def intersect(self, other: "Box") -> "Box | None":
        x0, y0 = max(self.x0, other.x0), max(self.y0, other.y0)
        x1, y1 = min(self.x1, other.x1), min(self.y1, other.y1)
        if x1 <= x0 or y1 <= y0:
            return None
        return Box(x0, y0, x1, y1)

    def intersects(self, other: "Box") -> bool:
        return self.intersect(other) is not None

    def contains(self, other: "Box", tol: float = 0.0) -> bool:
        return (other.x0 >= self.x0 - tol and other.y0 >= self.y0 - tol
                and other.x1 <= self.x1 + tol and other.y1 <= self.y1 + tol)

    def inset(self, top: float, right: float, bottom: float, left: float) -> "Box":
        return Box(self.x0 + left, self.y0 + bottom, self.x1 - right, self.y1 - top)

    def as_mm(self) -> list[float]:
        return [round(mm(v), 2) for v in (self.x0, self.y0, self.x1, self.y1)]


def _inherited(page_obj, key):
    node = page_obj
    for _ in range(64):
        if node is None:
            return None
        if key in node:
            return node[key]
        node = node.get("/Parent")
    return None


@dataclass(frozen=True)
class PageBoxes:
    media: Box
    crop: Box
    bleed: Box
    trim: Box
    has_trim: bool
    has_bleed: bool
    rotate: int


def page_boxes(page: pikepdf.Page) -> PageBoxes:
    obj = page.obj
    media = Box.from_array(_inherited(obj, "/MediaBox"))
    crop_raw = _inherited(obj, "/CropBox")
    crop = (Box.from_array(crop_raw).intersect(media) or media) if crop_raw is not None else media
    has_bleed = "/BleedBox" in obj
    has_trim = "/TrimBox" in obj or "/ArtBox" in obj
    bleed = (Box.from_array(obj["/BleedBox"]).intersect(media) or crop) if has_bleed else crop
    if "/TrimBox" in obj:
        trim = Box.from_array(obj["/TrimBox"])
    elif "/ArtBox" in obj:
        trim = Box.from_array(obj["/ArtBox"])
    else:
        trim = crop
    rotate = int(_inherited(obj, "/Rotate") or 0) % 360
    # Eine TrimBox, die identisch mit der MediaBox ist, hat keinen Informationswert
    if has_trim and _same_box(trim, media):
        has_trim = False
    return PageBoxes(media, crop, bleed, trim, has_trim, has_bleed, rotate)


def _same_box(a: Box, b: Box, tol: float = 0.01) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(
        (a.x0, a.y0, a.x1, a.y1), (b.x0, b.y0, b.x1, b.y1)))


# ---------------------------------------------------------------------------
# Matrizen
# ---------------------------------------------------------------------------

Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m1: Matrix, m2: Matrix) -> Matrix:
    """m1 × m2 (PDF-Konvention: Zeilenvektor * m1 * m2)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def min_scale(m: Matrix) -> float:
    """Kleinster Singulärwert des linearen Anteils (= stärkste Verkleinerung)."""
    a, b, c, d = m[:4]
    s1 = a * a + b * b + c * c + d * d
    det = a * d - b * c
    disc = math.sqrt(max(0.0, s1 * s1 - 4 * det * det))
    return math.sqrt(max(0.0, (s1 - disc) / 2))


def _matrix(arr) -> Matrix:
    vals = tuple(float(v) for v in arr)
    return vals if len(vals) == 6 else IDENTITY  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Farbräume
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorSpaceInfo:
    family: str              # Gray | RGB | CMYK | Spot | Lab | Pattern | Unknown
    components: int
    spot_names: tuple[str, ...] = ()
    registration: bool = False   # Separation "All" (Passermarkenfarbe)
    base: "ColorSpaceInfo | None" = None   # für Pattern mit Unterfarbraum
    obj: object = None           # Original (für Muster-Auflösung)


GRAY = ColorSpaceInfo("Gray", 1)
RGB = ColorSpaceInfo("RGB", 3)
CMYK = ColorSpaceInfo("CMYK", 4)
UNKNOWN = ColorSpaceInfo("Unknown", 1)

_DEVICE = {
    "/DeviceGray": GRAY, "/G": GRAY, "/CalGray": GRAY,
    "/DeviceRGB": RGB, "/RGB": RGB, "/CalRGB": RGB,
    "/DeviceCMYK": CMYK, "/CMYK": CMYK,
}


def classify_colorspace(cs, resources=None, depth: int = 0) -> ColorSpaceInfo:
    if depth > 8 or cs is None:
        return UNKNOWN
    if isinstance(cs, pikepdf.Name):
        name = str(cs)
        if name in _DEVICE:
            return _DEVICE[name]
        if name == "/Pattern":
            return ColorSpaceInfo("Pattern", 0)
        if resources is not None:
            named = resources.get("/ColorSpace")
            if named is not None and name in named:
                return classify_colorspace(named[name], resources, depth + 1)
        return UNKNOWN
    if isinstance(cs, pikepdf.Array) and len(cs) > 0:
        kind = str(cs[0])
        if kind in _DEVICE and len(cs) == 1:
            return _DEVICE[kind]
        if kind == "/ICCBased":
            stream = cs[1]
            n = int(stream.get("/N", 0))
            if n == 1:
                return GRAY
            if n == 3:
                return RGB
            if n == 4:
                return CMYK
            if "/Alternate" in stream:
                return classify_colorspace(stream["/Alternate"], resources, depth + 1)
            return UNKNOWN
        if kind in ("/CalRGB",):
            return RGB
        if kind in ("/CalGray",):
            return GRAY
        if kind == "/Lab":
            return ColorSpaceInfo("Lab", 3)
        if kind in ("/Indexed", "/I"):
            return classify_colorspace(cs[1], resources, depth + 1)
        if kind == "/Separation":
            name = str(cs[1])[1:]
            if name == "All":
                return ColorSpaceInfo("Spot", 1, ("All",), registration=True)
            if name == "None":
                return ColorSpaceInfo("None", 1)
            if name in PROCESS_NAMES:
                return ColorSpaceInfo("CMYK", 1)
            return ColorSpaceInfo("Spot", 1, (name,))
        if kind == "/DeviceN":
            names = [str(n)[1:] for n in cs[1]]
            spots = tuple(n for n in names if n not in PROCESS_NAMES and n != "None")
            if not spots:
                return ColorSpaceInfo("CMYK", len(names))
            if spots == ("All",):
                return ColorSpaceInfo("Spot", len(names), spots, registration=True)
            return ColorSpaceInfo("Spot", len(names), spots)
        if kind == "/Pattern":
            base = classify_colorspace(cs[1], resources, depth + 1) if len(cs) > 1 else None
            return ColorSpaceInfo("Pattern", base.components if base else 0, base=base)
    return UNKNOWN


def is_white(cs: ColorSpaceInfo, color: tuple[float, ...]) -> bool:
    if not color:
        return False
    if cs.family == "CMYK" or (cs.family == "Spot" and not cs.registration):
        return all(abs(v) < 1e-4 for v in color)
    if cs.family == "Gray":
        return abs(color[0] - 1.0) < 1e-4
    return False


def _initial_color(cs: ColorSpaceInfo) -> tuple[float, ...]:
    if cs.family == "CMYK" and cs.components == 4:
        return (0.0, 0.0, 0.0, 1.0)
    if cs.family in ("Spot", "CMYK"):
        return tuple([1.0] * cs.components)
    return tuple([0.0] * max(cs.components, 1))


# ---------------------------------------------------------------------------
# Ergebnisstrukturen
# ---------------------------------------------------------------------------

@dataclass
class ImagePlacement:
    name: str
    width_px: int
    height_px: int
    colorspace: ColorSpaceInfo
    bbox: Box
    ppi_x: float
    ppi_y: float
    is_mask: bool = False
    has_smask: bool = False
    inline: bool = False

    @property
    def ppi(self) -> float:
        return min(self.ppi_x, self.ppi_y)


@dataclass
class StrokeEvent:
    width_pt: float          # effektive Linienstärke auf der Seite
    bbox: Box
    segments: list | None    # nur bei einfachen geraden Pfaden (für Schnittmarken-Erkennung)
    colorspace: ColorSpaceInfo
    color: tuple


@dataclass
class OverprintEvent:
    kind: str                # fill | stroke | text
    bbox: Box | None
    colorspace: str


@dataclass
class PageContent:
    images: list[ImagePlacement] = field(default_factory=list)
    strokes: list[StrokeEvent] = field(default_factory=list)
    # Farbverwendung: family -> kind -> Anzahl   (kind: vector | text | image | shading)
    color_usage: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    spot_names: set = field(default_factory=set)
    registration_used: bool = False
    fonts_used: dict = field(default_factory=dict)        # objgen -> Font-Dictionary
    transparency: list[str] = field(default_factory=list)
    overprint_white: list[OverprintEvent] = field(default_factory=list)
    operations: int = 0
    truncated: bool = False

    def note_color(self, cs: ColorSpaceInfo, kind: str) -> None:
        if cs.family == "Pattern" and cs.base is not None:
            cs = cs.base
        if cs.family in ("None", "Pattern"):
            return
        self.color_usage[cs.family][kind] += 1
        if cs.registration:
            self.registration_used = True
        else:
            self.spot_names.update(cs.spot_names)

    def add_transparency(self, reason: str) -> None:
        if reason not in self.transparency:
            self.transparency.append(reason)


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

@dataclass
class _GState:
    ctm: Matrix = IDENTITY
    fill_cs: ColorSpaceInfo = GRAY
    stroke_cs: ColorSpaceInfo = GRAY
    fill_color: tuple = (0.0,)
    stroke_color: tuple = (0.0,)
    fill_pattern: object = None
    line_width: float = 1.0
    overprint_fill: bool = False
    overprint_stroke: bool = False
    font: object = None
    font_size: float = 0.0
    text_render: int = 0

    def copy(self) -> "_GState":
        return _GState(**self.__dict__)


_STROKE_OPS = {"S", "s", "B", "B*", "b", "b*"}
_FILL_OPS = {"f", "F", "f*", "B", "B*", "b", "b*"}
_TEXT_SHOW = {"Tj", "TJ", "'", '"'}


class _Interpreter:
    def __init__(self, result: PageContent):
        self.r = result
        self.stack: list[int] = []   # objgen von aktiven Form-XObjects (Zyklenschutz)

    # -- Einstieg -----------------------------------------------------------
    def run(self, content, resources, ctm: Matrix, depth: int = 0) -> None:
        if depth > MAX_DEPTH or self.r.truncated:
            return
        try:
            ops = pikepdf.parse_content_stream(content)
        except Exception:  # beschädigter Stream: Rest der Seite trotzdem prüfen
            return
        gs = _GState(ctm=ctm)
        gstack: list[_GState] = []
        path: list[list[tuple[float, float]]] = []
        curved = False
        for item in ops:
            self.r.operations += 1
            if self.r.operations > MAX_OPERATIONS:
                self.r.truncated = True
                return
            if isinstance(item, pikepdf.ContentStreamInlineImage):
                self._inline_image(item, gs, resources)
                continue
            operands, op = item.operands, str(item.operator)
            try:
                if op == "q":
                    gstack.append(gs.copy())
                elif op == "Q":
                    if gstack:
                        gs = gstack.pop()
                elif op == "cm":
                    gs.ctm = mat_mul(_matrix(operands), gs.ctm)
                elif op == "w":
                    gs.line_width = float(operands[0])
                elif op == "gs":
                    self._extgstate(operands[0], gs, resources)
                # Farben
                elif op == "cs":
                    gs.fill_cs = classify_colorspace(operands[0], resources)
                    gs.fill_color = _initial_color(gs.fill_cs)
                    gs.fill_pattern = None
                elif op == "CS":
                    gs.stroke_cs = classify_colorspace(operands[0], resources)
                    gs.stroke_color = _initial_color(gs.stroke_cs)
                elif op in ("sc", "scn"):
                    gs.fill_color, gs.fill_pattern = _color_operands(operands)
                elif op in ("SC", "SCN"):
                    gs.stroke_color, _ = _color_operands(operands)
                elif op == "g":
                    gs.fill_cs, gs.fill_color = GRAY, (float(operands[0]),)
                elif op == "G":
                    gs.stroke_cs, gs.stroke_color = GRAY, (float(operands[0]),)
                elif op == "rg":
                    gs.fill_cs, gs.fill_color = RGB, tuple(float(v) for v in operands)
                elif op == "RG":
                    gs.stroke_cs, gs.stroke_color = RGB, tuple(float(v) for v in operands)
                elif op == "k":
                    gs.fill_cs, gs.fill_color = CMYK, tuple(float(v) for v in operands)
                elif op == "K":
                    gs.stroke_cs, gs.stroke_color = CMYK, tuple(float(v) for v in operands)
                # Pfade
                elif op == "m":
                    path.append([apply(gs.ctm, float(operands[0]), float(operands[1]))])
                elif op == "l":
                    if path:
                        path[-1].append(apply(gs.ctm, float(operands[0]), float(operands[1])))
                elif op in ("c", "v", "y"):
                    if path:
                        nums = [float(v) for v in operands]
                        for i in range(0, len(nums), 2):
                            path[-1].append(apply(gs.ctm, nums[i], nums[i + 1]))
                        curved = True
                elif op == "h":
                    if path and len(path[-1]) > 1:
                        path[-1].append(path[-1][0])
                elif op == "re":
                    x, y, w, h = (float(v) for v in operands)
                    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
                    path.append([apply(gs.ctm, *p) for p in pts])
                elif op in _STROKE_OPS or op in _FILL_OPS or op == "n":
                    if op in _FILL_OPS:
                        self._paint_fill(gs, path, resources, depth)
                    if op in _STROKE_OPS:
                        self._paint_stroke(gs, path, curved)
                    path, curved = [], False
                # Text
                elif op == "Tf":
                    gs.font = _lookup(resources, "/Font", operands[0])
                    gs.font_size = float(operands[1])
                elif op == "Tr":
                    gs.text_render = int(operands[0])
                elif op in _TEXT_SHOW:
                    self._show_text(gs)
                # Objekte
                elif op == "Do":
                    self._do(operands[0], gs, resources, depth)
                elif op == "sh":
                    sh = _lookup(resources, "/Shading", operands[0])
                    if sh is not None:
                        self.r.note_color(classify_colorspace(sh.get("/ColorSpace"), resources), "shading")
            except (ValueError, TypeError, IndexError, KeyError, AttributeError):
                continue  # einzelne fehlerhafte Operation überspringen

    # -- Zustände -----------------------------------------------------------
    def _extgstate(self, name, gs: _GState, resources) -> None:
        egs = _lookup(resources, "/ExtGState", name)
        if egs is None:
            return
        if "/LW" in egs:
            gs.line_width = float(egs["/LW"])
        if "/OP" in egs:
            gs.overprint_stroke = bool(egs["/OP"])
            gs.overprint_fill = bool(egs.get("/op", egs["/OP"]))
        if "/op" in egs:
            gs.overprint_fill = bool(egs["/op"])
        ca = float(egs.get("/ca", 1.0))
        CA = float(egs.get("/CA", 1.0))
        if ca < 0.999 or CA < 0.999:
            self.r.add_transparency(f"Deckkraft {round(min(ca, CA) * 100)} %")
        bm = egs.get("/BM")
        if bm is not None:
            modes = [str(m) for m in (bm if isinstance(bm, pikepdf.Array) else [bm])]
            mode = modes[0] if modes else "/Normal"
            if mode not in ("/Normal", "/Compatible"):
                self.r.add_transparency(f"Füllmethode {mode[1:]}")
        smask = egs.get("/SMask")
        if smask is not None and not (isinstance(smask, pikepdf.Name) and str(smask) == "/None"):
            self.r.add_transparency("Weiche Maske (SMask)")

    # -- Malen ----------------------------------------------------------------
    def _paint_fill(self, gs: _GState, path, resources, depth) -> None:
        if not path:
            return
        self.r.note_color(gs.fill_cs, "vector")
        if gs.fill_cs.family == "Pattern":
            self._pattern(gs, resources, depth)
        if gs.overprint_fill and is_white(gs.fill_cs, gs.fill_color):
            self.r.overprint_white.append(
                OverprintEvent("fill", _path_bbox(path), gs.fill_cs.family))

    def _paint_stroke(self, gs: _GState, path, curved: bool) -> None:
        if not path:
            return
        self.r.note_color(gs.stroke_cs, "vector")
        width = gs.line_width * min_scale(gs.ctm)
        segments = None
        if not curved:
            segs = []
            for sub in path:
                segs.extend(zip(sub, sub[1:]))
            if len(segs) <= 4:
                segments = segs
        bbox = _path_bbox(path)
        if bbox is not None:
            self.r.strokes.append(StrokeEvent(width, bbox, segments, gs.stroke_cs, gs.stroke_color))
        if gs.overprint_stroke and is_white(gs.stroke_cs, gs.stroke_color):
            self.r.overprint_white.append(OverprintEvent("stroke", bbox, gs.stroke_cs.family))

    def _show_text(self, gs: _GState) -> None:
        mode = gs.text_render
        if mode in (3, 7):  # unsichtbarer Text (z. B. OCR-Ebene) wird nicht gedruckt
            return
        if gs.font is not None:
            try:
                key = gs.font.objgen
                if key == (0, 0):
                    key = id(gs.font)
            except AttributeError:
                key = id(gs.font)
            self.r.fonts_used.setdefault(key, gs.font)
        if mode in (0, 2, 4, 6):
            self.r.note_color(gs.fill_cs, "text")
            if gs.overprint_fill and is_white(gs.fill_cs, gs.fill_color):
                self.r.overprint_white.append(OverprintEvent("text", None, gs.fill_cs.family))
        if mode in (1, 2, 5, 6):
            self.r.note_color(gs.stroke_cs, "text")

    def _pattern(self, gs: _GState, resources, depth) -> None:
        pat = _lookup(resources, "/Pattern", gs.fill_pattern) if gs.fill_pattern is not None else None
        if pat is None:
            return
        ptype = int(pat.get("/PatternType", 0))
        if ptype == 2:
            sh = pat.get("/Shading")
            if sh is not None:
                self.r.note_color(classify_colorspace(sh.get("/ColorSpace"), resources), "shading")
        elif ptype == 1 and isinstance(pat, pikepdf.Stream):
            key = pat.objgen
            if key in self.stack:
                return
            self.stack.append(key)
            pres = pat.get("/Resources", resources)
            self.run(pat, pres, _matrix(pat.get("/Matrix", IDENTITY)), depth + 1)
            self.stack.pop()

    def _do(self, name, gs: _GState, resources, depth) -> None:
        xobj = _lookup(resources, "/XObject", name)
        if xobj is None:
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
            self._image(str(name), xobj, gs, resources)
        elif subtype == "/Form":
            key = xobj.objgen
            if key in self.stack:
                return
            self.stack.append(key)
            fres = xobj.get("/Resources", resources)
            ctm = mat_mul(_matrix(xobj.get("/Matrix", IDENTITY)), gs.ctm)
            group = xobj.get("/Group")
            self.run(xobj, fres, ctm, depth + 1)
            if group is not None and str(group.get("/S", "")) == "/Transparency" and "/SMask" in xobj:
                self.r.add_transparency("Transparenzgruppe mit Maske")
            self.stack.pop()

    def _image(self, name: str, img, gs: _GState, resources) -> None:
        is_mask = bool(img.get("/ImageMask", False))
        cs = gs.fill_cs if is_mask else classify_colorspace(img.get("/ColorSpace"), resources)
        if str(img.get("/Filter", "")) == "/JPXDecode" and "/ColorSpace" not in img:
            cs = UNKNOWN
        has_smask = "/SMask" in img or int(img.get("/SMaskInData", 0)) > 0
        if has_smask:
            self.r.add_transparency("Bild mit Alphakanal")
        self._place(name, int(img.get("/Width", 0)), int(img.get("/Height", 0)), cs, gs,
                    is_mask, has_smask, inline=False)

    def _inline_image(self, item, gs: _GState, resources) -> None:
        img = item.iimage
        try:
            is_mask = bool(img.image_mask)
        except Exception:
            is_mask = False
        if is_mask:
            cs = gs.fill_cs
        else:
            try:
                cs = classify_colorspace(pikepdf.Name(img.colorspace), resources)
            except Exception:
                cs = UNKNOWN
        self._place("(inline)", int(img.width), int(img.height), cs, gs, is_mask, False, inline=True)

    def _place(self, name, w_px, h_px, cs, gs: _GState, is_mask, has_smask, inline) -> None:
        a, b, c, d, e, f = gs.ctm
        corners = [apply(gs.ctm, x, y) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
        bbox = Box.from_points(corners)
        w_in = math.hypot(a, b) / 72
        h_in = math.hypot(c, d) / 72
        ppi_x = w_px / w_in if w_in > 0 else float("inf")
        ppi_y = h_px / h_in if h_in > 0 else float("inf")
        self.r.images.append(ImagePlacement(name, w_px, h_px, cs, bbox, ppi_x, ppi_y,
                                            is_mask, has_smask, inline))
        if not is_mask:
            self.r.note_color(cs, "image")


def _color_operands(operands) -> tuple[tuple, object]:
    values, pattern = [], None
    for v in operands:
        if isinstance(v, pikepdf.Name):
            pattern = v
        else:
            values.append(float(v))
    return tuple(values), pattern


def _lookup(resources, category: str, name):
    if resources is None or name is None:
        return None
    try:
        cat = resources.get(category)
        if cat is None:
            return None
        return cat.get(str(name))
    except (AttributeError, TypeError):
        return None


def _path_bbox(path) -> Box | None:
    pts = [p for sub in path for p in sub]
    return Box.from_points(pts) if pts else None


def analyze_page(page: pikepdf.Page) -> PageContent:
    result = PageContent()
    obj = page.obj
    resources = _inherited(obj, "/Resources")
    interp = _Interpreter(result)
    if "/Contents" in obj:
        interp.run(page, resources, IDENTITY)
    # Annotationen mit Erscheinungsbild, die gedruckt werden, sind Teil der Seite
    for annot in obj.get("/Annots", []) or []:
        try:
            if int(annot.get("/F", 0)) & 4 and "/AP" in annot:
                ap = annot["/AP"].get("/N")
                if isinstance(ap, pikepdf.Stream):
                    rect = Box.from_array(annot["/Rect"])
                    interp.run(ap, ap.get("/Resources", resources),
                               (1, 0, 0, 1, rect.x0, rect.y0), 1)
        except Exception:
            continue
    # Hinweis: Eine Transparenzgruppe auf Seitenebene allein (/Group) ist kein Hinweis
    # auf echte Transparenz – viele Programme setzen sie immer.
    return result
