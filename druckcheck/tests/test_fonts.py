import pikepdf

from druckcheck.checks.fonts import check_fonts, font_name, is_embedded
from druckcheck.models import Status

from conftest import a5_with_bleed


def test_embedded_font_green(build, open_doc):
    result = check_fonts(open_doc(build(lambda b: a5_with_bleed(b).text(20, 50, "Hallo")), "flyer_a5"))
    assert result.status == Status.GREEN
    assert result.measurements["fonts"][0]["embedded"] is True


def test_not_embedded_font_red(build, open_doc):
    result = check_fonts(open_doc(
        build(lambda b: a5_with_bleed(b).text(20, 50, "Hallo", embedded=False)), "flyer_a5"))
    assert result.status == Status.RED
    (f,) = result.findings
    assert f.code == "fonts.not_embedded" and f.data["font"] == "Helvetica"


def test_no_text_green(build, open_doc):
    result = check_fonts(open_doc(build(lambda b: a5_with_bleed(b)), "flyer_a5"))
    assert result.status == Status.GREEN
    assert "Pfade" in result.summary


def test_type3_and_type0_rules():
    pdf = pikepdf.new()
    t3 = pikepdf.Dictionary(Subtype=pikepdf.Name.Type3)
    assert is_embedded(t3)
    desc = pikepdf.Dictionary(FontFile2=pikepdf.Stream(pdf, b"x"))
    cid = pikepdf.Dictionary(Subtype=pikepdf.Name.CIDFontType2, FontDescriptor=desc)
    t0 = pikepdf.Dictionary(Subtype=pikepdf.Name.Type0, BaseFont=pikepdf.Name("/ABCDEF+Arial-Bold"),
                            DescendantFonts=[cid])
    assert is_embedded(t0)
    assert font_name(t0) == "Arial-Bold"
    t0_missing = pikepdf.Dictionary(Subtype=pikepdf.Name.Type0, DescendantFonts=[
        pikepdf.Dictionary(Subtype=pikepdf.Name.CIDFontType2, FontDescriptor=pikepdf.Dictionary())])
    assert not is_embedded(t0_missing)
