import pytest

from druckcheck.checks.marks import check_crop_marks, check_hairlines
from druckcheck.models import Status

from conftest import a5_with_bleed, codes


@pytest.mark.parametrize("width,status", [
    (0.0, Status.RED), (0.1, Status.RED), (0.2, Status.YELLOW), (0.25, Status.GREEN), (0.5, Status.GREEN),
])
def test_hairline_thresholds(build, open_doc, width, status):
    doc = open_doc(build(lambda b: a5_with_bleed(b).line(20, 50, 120, 50, width_pt=width)), "flyer_a5")
    assert check_hairlines(doc).status == status


def test_hairline_in_bleed_only_ignored(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b).line(20, 0.5, 120, 0.5, width_pt=0.05)), "flyer_a5")
    assert check_hairlines(doc).status == Status.GREEN


def test_hairline_at_scale_one_to_ten(build, open_doc):
    # 0,1 pt auf einer 1:10-Seite = 1 pt im Endformat → in Ordnung
    doc = open_doc(build(lambda b: b.page(356, 252).line(50, 50, 200, 50, width_pt=0.1)), "grossflaeche_18_1")
    assert check_hairlines(doc).status == Status.GREEN


def test_crop_marks_without_trimbox_red(build, open_doc):
    def fn(b):
        p = b.page(105 + 24, 148 + 24)
        p.rect(10, 10, 109, 152, cmyk=(0.2, 0, 0, 0))
        p.crop_marks((12, 12, 117, 160))
    result = check_crop_marks(open_doc(build(fn), "flyer_a6"))
    assert result.status == Status.RED
    assert result.findings[0].data["segments"] == 8


def test_crop_marks_outside_bleedbox_yellow(build, open_doc):
    def fn(b):
        p = b.page(105 + 24, 148 + 24)
        p.set_box("/TrimBox", 12, 12, 117, 160)
        p.set_box("/BleedBox", 10, 10, 119, 162)
        p.crop_marks((12, 12, 117, 160), offset_mm=3)
    result = check_crop_marks(open_doc(build(fn), "flyer_a6"))
    assert codes(result) == {"marks.crop_marks_outside"}


def test_crop_marks_not_counted_as_hairlines(build, open_doc):
    def fn(b):
        p = b.page(105 + 24, 148 + 24)
        p.crop_marks((12, 12, 117, 160), width_pt=0.1)
    assert check_hairlines(open_doc(build(fn), "flyer_a6")).status == Status.GREEN


def test_design_lines_are_not_crop_marks(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b)
        for y in range(20, 200, 20):        # kurze Linien im Motiv
            p.line(30, y, 40, y, width_pt=1)
    assert check_crop_marks(open_doc(build(fn), "flyer_a5")).status == Status.GREEN
