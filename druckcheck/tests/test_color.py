import dataclasses

import pytest

from druckcheck.checks.color import check_colorspaces, check_tac
from druckcheck.models import Status

from conftest import a5_with_bleed, codes


def test_cmyk_only_is_green(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b)
        p.image(10, 10, 50, 50, px=(600, 600), mode="CMYK")
        p.text(10, 100, "Text", cmyk=(0, 0, 0, 1))
    result = check_colorspaces(open_doc(build(fn), "flyer_a5"))
    assert result.status == Status.GREEN
    assert result.measurements["families"] == ["CMYK"]


@pytest.mark.parametrize("what", ["image", "vector", "text"])
def test_rgb_is_yellow(build, open_doc, what):
    def fn(b):
        p = a5_with_bleed(b)
        if what == "image":
            p.image(10, 10, 50, 50, px=(600, 600), mode="RGB")
        elif what == "vector":
            p.rect(10, 10, 20, 20, rgb=(1, 0, 0))
        else:
            p.text(10, 100, "Text", rgb=(0, 0, 1))
    result = check_colorspaces(open_doc(build(fn), "flyer_a5"))
    assert result.status == Status.YELLOW
    (f,) = result.findings
    assert f.code == "color.rgb" and what in f.data["kinds"]


def test_rgb_policy_error_is_red(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b).rect(1, 1, 5, 5, rgb=(1, 0, 0))), "flyer_a5")
    doc.product = dataclasses.replace(doc.product, rgb_policy="error")
    assert check_colorspaces(doc).status == Status.RED


def test_spot_color_and_registration(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b)
        p.spot_color("S1", "PANTONE 485 C", (0, 1, 1, 0))
        p.rect(10, 10, 20, 20, spot=("S1", 1))
        p.spot_color("Reg", "All")
        p.line(0, 0, 5, 0, width_pt=0.5, spot=("Reg", 1))
    result = check_colorspaces(open_doc(build(fn), "flyer_a5"))
    assert codes(result) == {"color.spot", "color.registration"}
    assert result.measurements["spot_names"] == ["PANTONE 485 C"]


def test_tac_ok(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b).rect(10, 10, 50, 50, cmyk=(0.6, 0.6, 0.6, 0.6))), "flyer_a5")
    result = check_tac(doc)
    assert result.status == Status.GREEN
    assert result.measurements["pages"][0]["max_tac"] == pytest.approx(240, abs=3)


def test_tac_exceeded_large_area_is_red(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b).rect(10, 10, 50, 50, cmyk=(1, 1, 1, 1))), "flyer_a5")
    result = check_tac(doc)
    assert result.status == Status.RED
    (f,) = result.findings
    assert f.data["max_tac"] == pytest.approx(400, abs=1)
    assert f.data["area_over_cm2"] == pytest.approx(25, rel=0.15)


def test_tac_exceeded_tiny_area_is_yellow(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b).rect(10, 10, 5, 5, cmyk=(1, 1, 1, 0.5))), "flyer_a5")
    assert check_tac(doc).status == Status.YELLOW


def test_tac_ignores_marks_outside_print_area(build, open_doc):
    def fn(b):
        p = b.page(105 + 24, 148 + 24)
        p.rect(10, 10, 109, 152, cmyk=(0.2, 0, 0, 0))
        p.crop_marks((12, 12, 117, 160), registration=True, width_pt=2)
    assert check_tac(open_doc(build(fn), "flyer_a6")).status == Status.GREEN


def test_tac_rotated_page(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b)
        p.rect(10, 10, 50, 50, cmyk=(1, 1, 1, 1))
        p.rotate = 90
    result = check_tac(open_doc(build(fn), "flyer_a5"))
    assert result.findings[0].data["area_over_cm2"] == pytest.approx(25, rel=0.15)
