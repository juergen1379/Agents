import pytest

from druckcheck.checks.images import check_image_resolution
from druckcheck.models import Status

from conftest import a5_with_bleed


def _a5_image(px, size_mm=(101.6, 101.6), pos=(20, 50)):
    def fn(b):
        p = a5_with_bleed(b)
        p.image(pos[0], pos[1], size_mm[0], size_mm[1], px=px)
    return fn


@pytest.mark.parametrize("px,status", [
    ((1200, 1200), Status.GREEN),    # 300 dpi
    ((1080, 1080), Status.YELLOW),   # 270 dpi
    ((400, 400), Status.RED),        # 100 dpi
])
def test_resolution_thresholds(build, open_doc, px, status):
    result = check_image_resolution(open_doc(build(_a5_image(px)), "flyer_a5"))
    assert result.status == status
    assert result.measurements["images"][0]["dpi"] == pytest.approx(px[0] / 4, rel=1e-3)


def test_product_specific_threshold(build, open_doc):
    # 120 dpi: für ein A1-Plakat gelb, für einen Flyer rot
    def fn(b):
        p = b.page(600, 847).set_trim_with_bleed(3)
        p.image(50, 50, 254, 254, px=(1200, 1200))
    assert check_image_resolution(open_doc(build(fn), "plakat_a1")).status == Status.YELLOW
    assert check_image_resolution(open_doc(build(_a5_image((480, 480))), "flyer_a5")).status == Status.RED


def test_scaled_artwork_resolution_in_final_size(build, open_doc):
    # 18/1 im Maßstab 1:10: 300 ppi auf der Seite = 30 dpi im Endformat → gelb (25–35)
    def fn(b):
        b.page(356, 252).image(0, 0, 356, 252, px=(4205, 2976))
    result = check_image_resolution(open_doc(build(fn), "grossflaeche_18_1"))
    assert result.measurements["images"][0]["dpi"] == pytest.approx(30, rel=0.01)
    assert result.status == Status.YELLOW


def test_image_outside_page_ignored(build, open_doc):
    result = check_image_resolution(open_doc(build(_a5_image((50, 50), pos=(400, 400))), "flyer_a5"))
    assert result.status == Status.GREEN
    assert result.measurements["images"] == []


def test_tiny_images_ignored(build, open_doc):
    result = check_image_resolution(open_doc(build(_a5_image((10, 10), size_mm=(3, 3))), "flyer_a5"))
    assert result.measurements["images"] == []


def test_no_images(build, open_doc):
    result = check_image_resolution(open_doc(build(lambda b: a5_with_bleed(b)), "flyer_a5"))
    assert result.status == Status.GREEN
    assert result.summary == "Keine Bilder im Dokument."
