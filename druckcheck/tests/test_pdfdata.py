import math

import pikepdf
import pytest

from druckcheck.pdfdata import (
    IDENTITY, Box, analyze_page, apply, classify_colorspace, is_white, mat_mul, min_scale, page_boxes,
)
from druckcheck.pdfbuilder import PT, make_image


# -- Geometrie / Matrizen ----------------------------------------------------

def test_box_operations():
    a = Box(0, 0, 10, 10)
    b = Box(5, 5, 20, 20)
    assert a.intersect(b) == Box(5, 5, 10, 10)
    assert a.intersect(Box(11, 11, 12, 12)) is None
    assert a.contains(Box(1, 1, 9, 9))
    assert not a.contains(b)
    assert a.inset(1, 2, 3, 4) == Box(4, 3, 8, 9)


def test_matrix_multiplication_and_scale():
    scale = (2, 0, 0, 3, 0, 0)
    move = (1, 0, 0, 1, 10, 20)
    m = mat_mul(scale, move)          # erst skalieren, dann verschieben
    assert apply(m, 1, 1) == (12, 23)
    assert mat_mul(IDENTITY, m) == m
    assert min_scale(scale) == pytest.approx(2)
    rot = (math.cos(0.5), math.sin(0.5), -math.sin(0.5), math.cos(0.5), 0, 0)
    assert min_scale(rot) == pytest.approx(1)


# -- Farbräume ----------------------------------------------------------------

def test_classify_device_and_icc():
    pdf = pikepdf.new()
    assert classify_colorspace(pikepdf.Name.DeviceRGB).family == "RGB"
    assert classify_colorspace(pikepdf.Name.DeviceCMYK).family == "CMYK"
    icc = pikepdf.Stream(pdf, b"\0" * 10)
    icc["/N"] = 3
    assert classify_colorspace(pikepdf.Array([pikepdf.Name.ICCBased, icc])).family == "RGB"
    icc["/N"] = 4
    assert classify_colorspace(pikepdf.Array([pikepdf.Name.ICCBased, icc])).family == "CMYK"


def test_classify_separation_devicen_indexed():
    sep = pikepdf.Array([pikepdf.Name.Separation, pikepdf.Name("/HKS 43 K"), pikepdf.Name.DeviceCMYK, 0])
    info = classify_colorspace(sep)
    assert info.family == "Spot" and info.spot_names == ("HKS 43 K",)
    allsep = pikepdf.Array([pikepdf.Name.Separation, pikepdf.Name.All, pikepdf.Name.DeviceCMYK, 0])
    assert classify_colorspace(allsep).registration
    black = pikepdf.Array([pikepdf.Name.Separation, pikepdf.Name.Black, pikepdf.Name.DeviceCMYK, 0])
    assert classify_colorspace(black).family == "CMYK"
    dn = pikepdf.Array([pikepdf.Name.DeviceN, [pikepdf.Name.Cyan, pikepdf.Name.Magenta],
                        pikepdf.Name.DeviceCMYK, 0])
    assert classify_colorspace(dn).family == "CMYK"
    dn_spot = pikepdf.Array([pikepdf.Name.DeviceN, [pikepdf.Name.Cyan, pikepdf.Name("/Gold")],
                             pikepdf.Name.DeviceCMYK, 0])
    assert classify_colorspace(dn_spot).spot_names == ("Gold",)
    idx = pikepdf.Array([pikepdf.Name.Indexed, pikepdf.Name.DeviceRGB, 1, b"\0\0\0\xff\xff\xff"])
    assert classify_colorspace(idx).family == "RGB"


def test_named_colorspace_resource():
    res = pikepdf.Dictionary(ColorSpace=pikepdf.Dictionary(CS0=pikepdf.Name.DeviceRGB))
    assert classify_colorspace(pikepdf.Name("/CS0"), res).family == "RGB"


def test_is_white():
    cmyk = classify_colorspace(pikepdf.Name.DeviceCMYK)
    gray = classify_colorspace(pikepdf.Name.DeviceGray)
    assert is_white(cmyk, (0, 0, 0, 0))
    assert not is_white(cmyk, (0, 0, 0, 1))
    assert is_white(gray, (1,))


# -- Seitenboxen ----------------------------------------------------------------

def test_page_boxes_defaults_and_trim(build):
    path = build(lambda b: b.page(152, 214).set_trim_with_bleed(2))
    with pikepdf.open(path) as pdf:
        boxes = page_boxes(pdf.pages[0])
        assert boxes.has_trim and boxes.has_bleed
        assert boxes.trim.as_mm() == [2.0, 2.0, 150.0, 212.0]
    path = build(lambda b: b.page(148, 210))
    with pikepdf.open(path) as pdf:
        boxes = page_boxes(pdf.pages[0])
        assert not boxes.has_trim
        assert boxes.trim == boxes.media


def test_trimbox_equal_to_mediabox_is_ignored(build):
    path = build(lambda b: b.page(148, 210).set_box("/TrimBox", 0, 0, 148, 210))
    with pikepdf.open(path) as pdf:
        assert not page_boxes(pdf.pages[0]).has_trim


# -- Interpreter ----------------------------------------------------------------

def _analyze(path):
    with pikepdf.open(path) as pdf:
        return analyze_page(pdf.pages[0])


def test_image_ppi_from_ctm(build):
    # 1200 px auf 101,6 mm (= 4 Zoll) → 300 ppi
    path = build(lambda b: b.page(150, 150).image(10, 10, 101.6, 50.8, px=(1200, 300)))
    content = _analyze(path)
    (img,) = content.images
    assert img.ppi_x == pytest.approx(300, rel=1e-3)
    assert img.ppi_y == pytest.approx(150, rel=1e-3)
    assert img.ppi == pytest.approx(150, rel=1e-3)
    assert img.colorspace.family == "CMYK"


def test_image_inside_scaled_form_xobject(build):
    def fn(b):
        p = b.page(200, 200)
        img = make_image(b.pdf, 600, 600, "RGB")
        form = pikepdf.Stream(b.pdf, f"q {100 * PT} 0 0 {100 * PT} 0 0 cm /I Do Q".encode())
        form["/Type"] = pikepdf.Name.XObject
        form["/Subtype"] = pikepdf.Name.Form
        form["/BBox"] = [0, 0, 1000, 1000]
        form["/Matrix"] = [0.5, 0, 0, 0.5, 0, 0]       # Form halbiert alles
        form["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(I=img))
        p.xobjects["Fm"] = form
        p.raw("q 2 0 0 2 0 0 cm /Fm Do Q")             # ... und wird wieder verdoppelt
    content = _analyze(build(fn))
    (img,) = content.images
    # 600 px auf 100 mm → 152,4 ppi
    assert img.ppi == pytest.approx(152.4, rel=1e-3)
    assert img.colorspace.family == "RGB"


def test_inline_image_detected(build):
    def fn(b):
        b.page(100, 100).raw("q 72 0 0 72 0 0 cm BI /W 2 /H 2 /CS /RGB /BPC 8 ID "
                             + "\0" * 12 + " EI Q")
    content = _analyze(build(fn))
    (img,) = content.images
    assert img.inline and img.width_px == 2
    assert img.ppi == pytest.approx(2)
    assert img.colorspace.family == "RGB"


def test_stroke_width_scaled_by_ctm(build):
    def fn(b):
        b.page(100, 100).raw("q 0.5 0 0 0.5 0 0 cm 0.4 w 0 0 0 1 K 10 10 m 100 10 l S Q")
    (stroke,) = _analyze(build(fn)).strokes
    assert stroke.width_pt == pytest.approx(0.2)
    assert stroke.segments is not None and len(stroke.segments) == 1


def test_fonts_only_recorded_when_text_shown(build):
    def fn(b):
        p = b.page(100, 100).text(10, 10, "Hallo", embedded=True)
        p.fonts["Unused"] = pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                               BaseFont=pikepdf.Name.Courier)
    with pikepdf.open(build(fn)) as pdf:
        content = analyze_page(pdf.pages[0])
        names = {str(f.BaseFont) for f in content.fonts_used.values()}
    assert names == {"/NimbusSans-Regular"}


def test_invisible_text_ignored(build):
    def fn(b):
        p = b.page(100, 100).text(10, 10, "x", embedded=False)
        p.ops[-1] = p.ops[-1].replace("BT", "BT 3 Tr")
    content = _analyze(build(fn))
    assert content.fonts_used == {}


def test_color_usage_and_transparency(build):
    def fn(b):
        p = b.page(100, 100)
        p.rect(0, 0, 10, 10, rgb=(1, 0, 0))
        p.text(10, 10, "x", cmyk=(0, 0, 0, 1))
        p.extgstate("M", BM="/Multiply")
        p.rect(0, 0, 10, 10, cmyk=(0, 1, 0, 0), gs="M")
    content = _analyze(build(fn))
    assert content.color_usage["RGB"]["vector"] == 1
    assert content.color_usage["CMYK"]["text"] == 1
    assert content.transparency == ["Füllmethode Multiply"]


def test_overprint_white_detected(build):
    def fn(b):
        p = b.page(100, 100)
        p.extgstate("OP", OP=True, op=True)
        p.rect(0, 0, 10, 10, cmyk=(0, 0, 0, 0), gs="OP")     # weiß + überdrucken → Fehler
        p.rect(0, 0, 10, 10, cmyk=(0, 0, 0, 1), gs="OP")     # schwarz überdrucken → ok
    content = _analyze(build(fn))
    assert len(content.overprint_white) == 1


def test_broken_content_does_not_crash(build):
    content = _analyze(build(lambda b: b.page(50, 50).raw("q 1 0 0 cm 5 w ) ( Tj Q /X Do")))
    assert content.images == []
