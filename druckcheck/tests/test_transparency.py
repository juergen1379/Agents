from druckcheck.checks.transparency import check_overprint, check_transparency
from druckcheck.models import Status

from conftest import a5_with_bleed


def test_no_transparency(build, open_doc):
    assert check_transparency(open_doc(build(lambda b: a5_with_bleed(b)), "flyer_a5")).status == Status.GREEN


def test_opacity_yellow(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b).extgstate("A", ca=0.5)
        p.rect(10, 10, 20, 20, cmyk=(1, 0, 0, 0), gs="A")
    result = check_transparency(open_doc(build(fn), "flyer_a5"))
    assert result.status == Status.YELLOW
    assert result.findings[0].data["reasons"] == ["Deckkraft 50 %"]


def test_image_with_alpha(build, open_doc):
    def fn(b):
        a5_with_bleed(b).image(10, 10, 30, 30, px=(300, 300), smask=True)
    result = check_transparency(open_doc(build(fn), "flyer_a5"))
    assert "Bild mit Alphakanal" in result.findings[0].data["reasons"]


def test_page_group_alone_is_not_transparency(build, open_doc):
    import pikepdf

    path = build(lambda b: a5_with_bleed(b))
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj["/Group"] = pikepdf.Dictionary(S=pikepdf.Name.Transparency)
        pdf.save(path)
    assert check_transparency(open_doc(path, "flyer_a5")).status == Status.GREEN


def test_white_overprint_red(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b).extgstate("OP", OP=True, op=True)
        p.text(20, 100, "Weiß", cmyk=(0, 0, 0, 0), gs="OP")
    result = check_overprint(open_doc(build(fn), "flyer_a5"))
    assert result.status == Status.RED
    assert result.findings[0].data["kinds"] == ["Text"]


def test_black_overprint_fine(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b).extgstate("OP", OP=True, op=True)
        p.text(20, 100, "Schwarz", cmyk=(0, 0, 0, 1), gs="OP")
    assert check_overprint(open_doc(build(fn), "flyer_a5")).status == Status.GREEN
